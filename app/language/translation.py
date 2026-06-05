import re
import unicodedata


class BilingualTextNormalizer:
    """Small deterministic bridge for Vietnamese/English learner text."""

    REQUEST_TRANSLATIONS = (
        ("menh de quan he", "relative clause"),
        ("cau dieu kien", "conditional sentence"),
        ("tu vung du lich", "travel vocabulary"),
        ("cau bi dong", "passive voice"),
        ("bi dong", "passive voice"),
        ("trac nghiem", "multiple choice"),
        ("multiple choice", "multiple choice"),
        ("dien vao cho trong", "fill in the blank"),
        ("dien cho trong", "fill in the blank"),
        ("dien khuyet", "fill in the blank"),
        ("dien tu", "fill in the blank"),
        ("tu vung", "vocabulary"),
        ("ngu phap", "grammar"),
        ("du lich", "travel"),
        ("do kho de", "easy"),
        ("muc de", "easy"),
        ("cap do de", "easy"),
        ("co ban", "easy"),
        ("trung binh", "medium"),
        ("muc vua", "medium"),
        ("vua", "medium"),
        ("do kho kho", "hard"),
        ("muc kho", "hard"),
        ("nang cao", "hard"),
        ("kho", "hard"),
        ("giai thich", "explain"),
        ("sinh bai", "generate exercises"),
        ("tao bai", "generate exercises"),
        ("tao", "generate"),
        ("luyen", "practice"),
    )

    ANSWER_TRANSLATIONS = (
        ("hom nay", "today"),
        ("ngay mai", "tomorrow"),
        ("hom qua", "yesterday"),
        ("bay gio", "now"),
        ("tuan truoc", "last week"),
        ("tuan sau", "next week"),
        ("thang truoc", "last month"),
        ("thang sau", "next month"),
        ("o nha", "at home"),
        ("o truong", "at school"),
        ("o cong ty", "at work"),
        ("buoi sang", "morning"),
        ("buoi chieu", "afternoon"),
        ("buoi toi", "evening"),
        ("mau do", "red"),
        ("mau xanh", "blue"),
        ("mau vang", "yellow"),
        ("dung", "correct"),
        ("sai", "incorrect"),
    )

    VIETNAMESE_CUES = (
        "cau",
        "bai",
        "tao",
        "luyen",
        "trac nghiem",
        "dien khuyet",
        "bi dong",
        "menh de",
        "tu vung",
        "ngu phap",
        "muc",
        "do kho",
    )

    NUMBER_WORDS = {
        "mot": 1,
        "hai": 2,
        "ba": 3,
        "bon": 4,
        "tu": 4,
        "nam": 5,
        "sau": 6,
        "bay": 7,
        "tam": 8,
        "chin": 9,
        "muoi": 10,
    }

    _VIETNAMESE_ACCENT_RE = re.compile(
        r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễ"
        r"ìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
        r"ùúụủũưừứựửữỳýỵỷỹđ"
        r"ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄ"
        r"ÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠ"
        r"ÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
    )

    def detect_language(self, text: str) -> str:
        normalized = self.normalize_for_matching(text)
        if self._VIETNAMESE_ACCENT_RE.search(text):
            return "vi"
        if any(cue in normalized for cue in self.VIETNAMESE_CUES):
            return "vi"
        return "en"

    def request_to_processing_text(self, text: str) -> str:
        normalized = self.normalize_for_matching(text)
        normalized = self._replace_number_words_before_question_words(normalized)
        return self._apply_translations(normalized, self.REQUEST_TRANSLATIONS)

    def answer_to_processing_text(self, text: str) -> str:
        normalized = self.normalize_for_matching(text)
        return self._apply_translations(normalized, self.ANSWER_TRANSLATIONS)

    def answers_match(self, selected_answer: str | None, correct_answer: str) -> bool:
        if selected_answer is None:
            return False

        selected_variants = self._answer_variants(selected_answer)
        correct_variants = self._answer_variants(correct_answer)
        return bool(selected_variants.intersection(correct_variants))

    def normalize_for_matching(self, text: str) -> str:
        text = text.replace("đ", "d").replace("Đ", "D")
        text = unicodedata.normalize("NFD", text)
        text = "".join(
            character
            for character in text
            if unicodedata.category(character) != "Mn"
        )
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return self._collapse_spaces(text)

    def _replace_number_words_before_question_words(self, text: str) -> str:
        question_words = "cau|cau hoi|question|questions|bai|bai tap"
        for word, number in self.NUMBER_WORDS.items():
            text = re.sub(
                rf"\b{word}\s+({question_words})\b",
                rf"{number} \1",
                text,
            )
        return text

    def _apply_translations(
        self,
        text: str,
        translations: tuple[tuple[str, str], ...],
    ) -> str:
        translated = f" {text} "
        for source, target in translations:
            translated = re.sub(
                rf"(?<!\w){re.escape(source)}(?!\w)",
                f" {target} ",
                translated,
            )
        return self._collapse_spaces(translated)

    def _answer_variants(self, text: str) -> set[str]:
        normalized = self.normalize_for_matching(text)
        translated = self.answer_to_processing_text(text)
        return {
            variant
            for variant in (normalized, translated)
            if variant
        }

    def _collapse_spaces(self, text: str) -> str:
        return " ".join(text.strip().split())
