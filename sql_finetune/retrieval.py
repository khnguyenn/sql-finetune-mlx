"""Deterministic BM25 retrieval over trusted question/SQL training examples."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from .common import messages


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class ExampleRetriever:
    def __init__(self, corpus):
        source = Path(corpus).read_bytes()
        self.sha256 = hashlib.sha256(source).hexdigest()
        self.documents = []
        for line, row in enumerate(source.decode().splitlines(), 1):
            conversation = json.loads(row)["messages"]
            if [message["role"] for message in conversation] != ["system", "user", "assistant"]:
                raise ValueError(f"Corpus line {line} must be a system/user/assistant training example")
            if any(not isinstance(message["content"], str) or not message["content"].strip() for message in conversation):
                raise ValueError(f"Corpus line {line} has empty or invalid content")
            self.documents.append({
                "line": line, "input": conversation[1]["content"],
                "sql": conversation[2]["content"],
            })
        if not self.documents:
            raise ValueError("Retrieval corpus is empty")
        # Index inputs only. Answers and family metadata never influence ranking.
        self.counts = [Counter(tokens(doc["input"])) for doc in self.documents]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average_length = sum(self.lengths) / len(self.lengths)
        if not self.average_length:
            raise ValueError("Retrieval corpus contains no searchable tokens")
        self.frequency = Counter(term for count in self.counts for term in count)

    def retrieve(self, schema, question, k=3):
        if k < 1:
            raise ValueError("Retrieval top-k must be positive")
        target = messages(schema, question)[1]["content"]
        terms = set(tokens(target))
        ranked = []
        for document, counts, length in zip(self.documents, self.counts, self.lengths):
            if document["input"].strip() == target.strip():
                continue
            score = 0.0
            for term in sorted(terms):
                count = counts[term]
                if count:
                    idf = math.log(1 + (len(self.documents) - self.frequency[term] + 0.5) / (self.frequency[term] + 0.5))
                    score += idf * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / self.average_length))
            if score > 0:
                ranked.append({**document, "score": score})
        ranked.sort(key=lambda doc: (-doc["score"], doc["line"]))
        return ranked[:k]


def retrieval_messages(schema, question, examples):
    conversation = messages(schema, question)
    if examples:
        context = "\n\n".join(f"Example {index}:\n{doc['input']}\nSQL:\n{doc['sql']}" for index, doc in enumerate(examples, 1))
        conversation[1]["content"] = (
            "Retrieved training examples follow. Adapt the pattern to the final question's schema; "
            "return SQL for the final question only.\n\n"
            + context + "\n\nFinal question:\n" + conversation[1]["content"]
        )
    return conversation
