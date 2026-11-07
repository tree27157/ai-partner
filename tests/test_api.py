from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_chat_returns_sources():
    """主链路：能回答，且带来源"""
    r = client.post("/chat", json={"question": "虚拟内存和分页的区别"})

    assert r.status_code == 200, r.text
    body = r.json()

    assert body["session_id"], "session_id 不该为空"
    assert body["sources"], "应该至少有一条来源"

    for s in body["sources"]:
        assert set(s) == {"file", "score"}
        assert s["score"] >= 0.3


def test_chat_unknown_session_404():
    """不存在的 session_id 应返回 404"""
    r = client.post("/chat", json={"question": "hi", "session_id": "not-exist"})
    assert r.status_code == 404, r.text