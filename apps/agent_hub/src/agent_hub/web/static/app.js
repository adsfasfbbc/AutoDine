(function () {
  "use strict";

  const AGENT = document.body.dataset.agent;
  const chatEl = document.getElementById("chat");
  const formEl = document.getElementById("composer");
  const inputEl = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const clearBtn = document.getElementById("clear");

  const GREETING = {
    consumer: "你好，我是消费者点餐助手。可以帮你浏览菜单、推荐饮品、下单和查单。",
    kitchen: "你好，我是后厨助手。可以帮你查看生产任务与领料清单，并推进生产状态。",
    manager: "你好，我是店长助手。可以帮你查库存/质量、告警、排队和运营总结。",
  }[AGENT] || "你好，请问有什么可以帮你？";

  let history = [];

  function scrollBottom() {
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function addHint(text) {
    const wrap = document.createElement("div");
    wrap.className = "msg hint";
    wrap.textContent = text;
    chatEl.appendChild(wrap);
    scrollBottom();
  }

  function addBubble(role, text) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + role;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    chatEl.appendChild(wrap);
    scrollBottom();
    return bubble;
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text || sendBtn.disabled) return;
    inputEl.value = "";
    addBubble("user", text);

    const priorHistory = history.slice();
    const typing = addBubble("agent", "思考中…");
    sendBtn.disabled = true;

    try {
      const resp = await fetch("/api/v1/agents/" + AGENT + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: priorHistory }),
      });

      let reply;
      try {
        const data = await resp.json();
        reply = data.reply;
        if (!resp.ok) reply = reply || ("出错了：" + (data.detail || resp.status));
      } catch (e) {
        reply = "服务返回异常（HTTP " + resp.status + "），请查看服务端日志。";
      }

      typing.textContent = reply || "（未收到回复）";
      scrollBottom();

      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: reply || "" });
    } catch (err) {
      typing.textContent =
        "⚠️ 无法连接 Agent Hub 服务。请通过下面的命令启动服务后，再访问 http://localhost:8100/consumer：\n" +
        "  py -3.11 -m uvicorn agent_hub.service:create_app --factory --port 8100";
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    send();
  });

  clearBtn.addEventListener("click", function () {
    history = [];
    chatEl.innerHTML = "";
    addHint("已清空对话，开始新的对话吧。");
    inputEl.focus();
  });

  if (location.protocol === "file:") {
    addHint(
      "⚠️ 检测到你是直接打开 HTML 文件，无法连接后端。\n" +
        "请先在终端运行：\n" +
        "  py -3.11 -m uvicorn agent_hub.service:create_app --factory --port 8100\n" +
        "然后用浏览器访问 http://localhost:8100/consumer"
    );
  } else {
    addHint(GREETING);
  }
  inputEl.focus();
})();
