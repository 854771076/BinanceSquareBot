from dataclasses import dataclass


@dataclass(frozen=True)
class TweetContentValidator:
    """Validates generated text per post_type.

    coin_whitelist, when provided, restricts which $SYMBOL tags the output may
    contain. Any $-prefixed token not in the whitelist fails validation — this
    is the enforcement point for accurate coin association.
    """

    min_chars: int
    max_chars: int
    max_hashtags: int
    max_mentions: int
    article_min_chars: int = 800
    article_max_chars: int = 15000
    article_min_title: int = 10
    article_max_title: int = 100
    coin_whitelist: tuple[str, ...] = ()
    post_type: str = "text"

    def validate(self, content: str) -> None:
        text = content.strip()
        errors: list[str] = []

        if not text:
            errors.append("输出为空")

        if self.post_type == "article":
            min_c, max_c = self.article_min_chars, self.article_max_chars
        elif self.post_type == "video":
            min_c, max_c = 1, self.max_chars
        else:  # text / image short captions
            min_c, max_c = self.min_chars, self.max_chars

        length = len(text)
        if length < min_c or length > max_c:
            errors.append(f"字符数必须在 {min_c}-{max_c} 之间，当前 {length}")

        if text.count("#") > self.max_hashtags and self.post_type != "article":
            errors.append(f"话题标签不能超过 {self.max_hashtags} 个")

        if text.count("$") > self.max_mentions and self.post_type != "article":
            errors.append(f"代币标签不能超过 {self.max_mentions} 个")

        if "```" in text:
            errors.append("不能包含 Markdown 代码块")

        if self.post_type != "article":
            wrapper_prefixes = ("以下是推文", "推文如下", "这是推文", "当然", "好的")
            if text.startswith(wrapper_prefixes):
                errors.append("不能包含包装说明")

        # Coin whitelist enforcement — when provided, every $TOKEN in the output
        # must be on the list. When empty, fall back to max_mentions count only
        # (backward-compat for sources without structured coin metadata).
        if self.coin_whitelist:
            allowed = {c.upper() for c in self.coin_whitelist}
            for token in _extract_dollar_tokens(text):
                if token.upper() not in allowed:
                    errors.append(
                        f"包含未授权的代币标签 ${token}（仅允许: {', '.join(sorted(allowed))}）"
                    )
                    break

        if errors:
            raise ValueError("；".join(errors))

    def validate_title(self, title: str | None) -> None:
        """Article title length check — called separately from body validation."""
        if self.post_type != "article":
            return
        if not title or not title.strip():
            raise ValueError("文章标题缺失")
        tlen = len(title.strip())
        if tlen < self.article_min_title or tlen > self.article_max_title:
            raise ValueError(
                f"标题长度必须在 {self.article_min_title}-{self.article_max_title} 之间，"
                f"当前 {tlen}"
            )


def _extract_dollar_tokens(text: str) -> list[str]:
    """Extract $SYMBOL tokens (letters/digits, 2-20 chars)."""
    tokens: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "$":
            j = i + 1
            while j < len(text) and (text[j].isalnum()):
                j += 1
            tok = text[i + 1 : j]
            if 2 <= len(tok) <= 20:
                tokens.append(tok)
            i = j
        else:
            i += 1
    return tokens
