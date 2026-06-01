from dataclasses import dataclass


@dataclass(frozen=True)
class TweetContentValidator:
    min_chars: int
    max_chars: int
    max_hashtags: int
    max_mentions: int

    def validate(self, content: str) -> None:
        text = content.strip()
        errors: list[str] = []

        if not text:
            errors.append("输出为空")

        length = len(text)
        if length < self.min_chars or length > self.max_chars:
            errors.append(
                f"字符数必须在 {self.min_chars}-{self.max_chars} 之间，当前 {length}"
            )

        if text.count("#") > self.max_hashtags:
            errors.append(f"话题标签不能超过 {self.max_hashtags} 个")

        if text.count("$") > self.max_mentions:
            errors.append(f"代币标签不能超过 {self.max_mentions} 个")

        if "```" in text:
            errors.append("不能包含 Markdown 代码块")

        wrapper_prefixes = ("以下是推文", "推文如下", "这是推文", "当然", "好的")
        if text.startswith(wrapper_prefixes):
            errors.append("不能包含包装说明")

        if errors:
            raise ValueError("；".join(errors))
