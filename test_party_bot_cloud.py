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


if __name__ == "__main__":
    unittest.main()
