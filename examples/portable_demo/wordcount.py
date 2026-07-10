"""Tiny self-contained module: count words in a string."""
def word_count(text: str) -> int:
    return len(text.split())

def unique_words(text: str) -> int:
    return len({w.lower() for w in text.split()})

if __name__ == "__main__":
    import sys
    print(word_count(" ".join(sys.argv[1:])))
