import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


def normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    title: str
    locator: str
    public_url: str | None = None


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    category: Literal[
        "summary", "experience", "skills", "education", "languages", "projects", "links", "training"
    ]
    entity: str
    tags: list[str] = Field(min_length=1, max_length=50)
    text_es: str = Field(min_length=8, max_length=1400)
    text_en: str = Field(min_length=8, max_length=1400)
    source_ids: list[str] = Field(min_length=1)

    def text(self, language: str) -> str:
        return self.text_en if language == "en" else self.text_es


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    approved: bool = False
    review_notes: list[str] = []
    public_links: list[str]
    sources: list[Source]
    facts: list[Fact] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self):
        sources = {s.id for s in self.sources}
        if len(sources) != len(self.sources) or len({f.id for f in self.facts}) != len(self.facts):
            raise ValueError("Duplicate source or fact ID")
        links = set(self.public_links)
        for link in links:
            parsed = urlsplit(link)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Public links must be credential-free HTTPS URLs")
        for source in self.sources:
            if source.public_url and source.public_url not in links:
                raise ValueError("Source URL must be an approved public link")
        for fact in self.facts:
            if not set(fact.source_ids) <= sources:
                raise ValueError(f"Unknown source in {fact.id}")
            for text in (fact.text_es, fact.text_en):
                if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|(?:\+?\d[\s().-]*){9,}", text):
                    raise ValueError(f"Email or phone-like value in {fact.id}")
                if any(unicodedata.category(c) == "Cf" for c in text):
                    raise ValueError(f"Invisible format characters in {fact.id}")
                for url in re.findall(r"https?://[^\s)]+", text):
                    if url.rstrip(".,") not in links:
                        raise ValueError(f"Unapproved URL in {fact.id}")
        return self

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:16]

    @classmethod
    def load(cls, path: Path) -> "Profile":
        return cls.model_validate(json.loads(path.read_text()))
