"""简单测试脚本 — 用于验证动态 trace"""


class Router:
    def dispatch(self, method: str):
        if method == "hello":
            return self.handle_hello()
        elif method == "bye":
            return self.handle_bye()
        else:
            return self.handle_unknown(method)

    def handle_hello(self):
        return greet("World")

    def handle_bye(self):
        return "Goodbye!"

    def handle_unknown(self, method):
        return f"Unknown: {method}"


def greet(name: str) -> str:
    msg = build_message(name)
    return msg


def build_message(name: str) -> str:
    return f"Hello, {name}!"


def main():
    r = Router()
    print(r.dispatch("hello"))
    print(r.dispatch("bye"))
    print(r.dispatch("unknown_method"))


if __name__ == "__main__":
    main()
