import threading
import unittest
from unittest.mock import patch
import party_bot_cloud as pbc


class TestPartyBotCloud(unittest.TestCase):
    def setUp(self):
        pbc._cached_state = pbc._default_state()
        pbc._welcomed_user_keys.clear()
        pbc._welcomed_groups.clear()
        pbc._welcome_buffers.clear()

    @patch("party_bot_cloud.tg_api")
    @patch("party_bot_cloud._push_cloud_state_async")
    def test_10_concurrent_guests_quiz_and_rsvp(self, mock_push, mock_tg):
        mock_tg.return_value = {"ok": True, "result": {"message_id": 100}}

        # Simulate 10 guests answering all 7 questions concurrently (some starting at Q4 in group chat)
        def simulate_guest(guest_idx: int):
            uid = 1000 + guest_idx
            fname = f"Гість_{guest_idx}"
            # RSVP
            status = "going" if guest_idx <= 8 else "maybe"
            pbc.handle_update({
                "callback_query": {
                    "id": f"cb_rsvp_{uid}",
                    "data": f"rsvp:{status}",
                    "from": {"id": uid, "first_name": fname, "username": f"user{uid}"},
                    "message": {"message_id": 50, "chat": {"id": -100999, "type": "supergroup"}},
                }
            })
            # Answer all 7 questions starting from different question offsets
            order = [((q + guest_idx) % 7) + 1 for q in range(7)]
            for qid in order:
                q_obj = next(q for q in pbc.QUIZ_QUESTIONS if q["id"] == qid)
                # Guest 1 gets all 7 right, others get (7 - guest_idx % 5) right
                choose_correct = (qid <= (7 - (guest_idx % 4)))
                sel_idx = q_obj["correct_index"] if choose_correct else (q_obj["correct_index"] + 1) % 4
                pbc.handle_update({
                    "callback_query": {
                        "id": f"cb_q_{uid}_{qid}",
                        "data": f"quiz:ans:{qid}:{sel_idx}",
                        "from": {"id": uid, "first_name": fname, "username": f"user{uid}"},
                        "message": {"message_id": 50, "chat": {"id": -100999, "type": "supergroup"}},
                    }
                })

        threads = [threading.Thread(target=simulate_guest, args=(i,)) for i in range(1, 11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = pbc.get_state()
        self.assertEqual(len(state["rsvp"]), 10)
        self.assertEqual(len(state["quiz_answers"]), 10)
        for i in range(1, 11):
            uid_str = str(1000 + i)
            self.assertEqual(len(state["quiz_answers"][uid_str]["answers"]), 7)

        leaderboard_txt = pbc.format_leaderboard(state)
        self.assertIn("Гість_4", leaderboard_txt)  # 4 % 4 == 0 -> 7/7 points
        self.assertIn("7 із 7 балів", leaderboard_txt)

    def test_atomic_merge_states_preserves_all_users(self):
        st_a = pbc._default_state()
        st_b = pbc._default_state()

        st_a["quiz_answers"]["101"] = {
            "name": "Олена",
            "username": "olena",
            "answers": {"1": {"sel": 2, "ok": True}, "2": {"sel": 2, "ok": True}},
        }
        st_b["quiz_answers"]["101"] = {
            "name": "Олена",
            "username": "olena",
            "answers": {"3": {"sel": 1, "ok": True}},
        }
        st_b["quiz_answers"]["202"] = {
            "name": "Андрій",
            "username": "andriy",
            "answers": {"1": {"sel": 0, "ok": False}},
        }

        merged = pbc._merge_states(st_a, st_b)
        self.assertEqual(len(merged["quiz_answers"]["101"]["answers"]), 3)
        self.assertIn("202", merged["quiz_answers"])

    @patch("party_bot_cloud.tg_api")
    def test_deep_link_personal_quiz_and_admin_hiding(self, mock_tg):
        mock_tg.return_value = {"ok": True, "result": {"message_id": 101}}

        # Regular guest sends /start quiz in private chat
        pbc.handle_update({
            "message": {
                "message_id": 1,
                "from": {"id": 999111, "first_name": "Марія"},
                "chat": {"id": 999111, "type": "private"},
                "text": "/start quiz",
            }
        })
        last_call = mock_tg.call_args_list[-1]
        self.assertEqual(last_call[0][0], "sendMessage")
        self.assertIn("Святкова вікторина про Алісу", last_call[0][1]["text"])

        # Regular guest sends /start in private chat -> should NOT see admin buttons
        pbc.handle_update({
            "message": {
                "message_id": 2,
                "from": {"id": 999111, "first_name": "Марія"},
                "chat": {"id": 999111, "type": "private"},
                "text": "/start",
            }
        })
        kb_json = str(mock_tg.call_args_list[-1][0][1]["reply_markup"])
        self.assertNotIn("admin:panel", kb_json)
        self.assertNotIn("admin:test_welcome", kb_json)

    @patch("party_bot_cloud.tg_api")
    def test_new_member_auto_deletes_service_msg_and_keeps_group_quiet(self, mock_tg):
        mock_tg.return_value = {"ok": True, "result": {"message_id": 999}}

        # Guest joins group
        pbc.handle_update({
            "message": {
                "message_id": 777,
                "chat": {"id": -100999, "type": "supergroup"},
                "new_chat_members": [{"id": 555111, "first_name": "Іван", "is_bot": False}],
            }
        })

        # 1. Check that service message 777 was deleted from group -100999
        delete_calls = [c for c in mock_tg.call_args_list if c[0][0] == "deleteMessage"]
        self.assertTrue(any(c[0][1]["chat_id"] == -100999 and c[0][1]["message_id"] == 777 for c in delete_calls))

        # 2. Check that NO sendMessage was sent to the group chat -100999
        send_calls_group = [c for c in mock_tg.call_args_list if c[0][0] == "sendMessage" and c[0][1].get("chat_id") == -100999]
        self.assertEqual(len(send_calls_group), 0, "Group chat must not receive any welcome spam!")

        # 3. Check that welcome message was directed to the user's private chat
        send_calls_user = [c for c in mock_tg.call_args_list if c[0][0] == "sendMessage" and c[0][1].get("chat_id") == 555111]
        self.assertEqual(len(send_calls_user), 1, "User should receive a private welcome message!")

    @patch("party_bot_cloud.tg_api")
    @patch("party_bot_cloud._push_cloud_state_async")
    def test_reset_user_quiz_command_and_merge(self, mock_push, mock_tg):
        mock_tg.return_value = {"ok": True, "result": {"message_id": 102}}

        state = pbc.get_state()
        state["quiz_answers"]["7386906127"] = {
            "name": "Svitlana",
            "username": "",
            "answers": {"1": {"sel": 1, "ok": True}},
        }
        state["quiz_answers"]["356753494"] = {
            "name": "Iryna Koziaryk",
            "username": "iryna_kozyarik",
            "answers": {"1": {"sel": 1, "ok": True}},
        }

        # Admin runs /reset_user Svitlana
        pbc.handle_update({
            "message": {
                "message_id": 10,
                "from": {"id": pbc.ADMIN_ID},
                "chat": {"id": pbc.ADMIN_ID, "type": "private"},
                "text": "/reset_user Svitlana",
            }
        })

        self.assertNotIn("7386906127", state["quiz_answers"])
        self.assertIn("356753494", state["quiz_answers"])
        self.assertIn("7386906127", state.get("quiz_reset_users", {}))

        # Simulate state merge with an older state that still had Svitlana
        st_old = pbc._default_state()
        st_old["quiz_answers"]["7386906127"] = {
            "name": "Svitlana",
            "username": "",
            "answers": {"1": {"sel": 1, "ok": True}},
        }
        merged = pbc._merge_states(st_old, state)
        self.assertNotIn("7386906127", merged["quiz_answers"], "Reset user must not be revived by state merge!")


if __name__ == "__main__":
    unittest.main()
