from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .hub import AgentHub


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_hub", description="AutoDine Agent Hub CLI")
    parser.add_argument("agent", nargs="?", help="agent 名称：consumer | kitchen | manager")
    parser.add_argument("message", nargs="*", help="发送给 agent 的消息")
    parser.add_argument("--list", action="store_true", help="列出所有可用 agent 及其工具")
    parser.add_argument("--chat", action="store_true", help="进入交互式对话")
    return parser


def _repl(hub: AgentHub, agent_name: str) -> None:
    print(f"进入与 {agent_name} 的对话（输入 exit 退出）")
    while True:
        try:
            message = input("you> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not message.strip():
            continue
        if message.strip().lower() in ("exit", "quit", "q"):
            break
        reply = hub.run(agent_name, message)
        print(f"{agent_name}> {reply}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    hub = AgentHub()
    try:
        if args.list:
            for entry in hub.describe():
                print(f"{entry['name']}: {', '.join(entry['tools'])}")
            return 0

        if args.chat:
            if not args.agent:
                parser.error("--chat 需要指定 agent 名称")
            _repl(hub, args.agent)
            return 0

        if not args.agent:
            parser.error("请提供 agent 名称（consumer | kitchen | manager），或用 --list 查看")

        message = " ".join(args.message)
        if not message:
            _repl(hub, args.agent)
            return 0

        print(hub.run(args.agent, message))
        return 0
    finally:
        hub.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
