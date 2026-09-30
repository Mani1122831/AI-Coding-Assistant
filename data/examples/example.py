"""
Example Python file for testing the AI Coding Assistant.
Upload this file in the 'Analyze File' feature.
"""


def fibonacci(n: int) -> list[int]:
    """Return the first n Fibonacci numbers."""
    if n <= 0:
        return []
    sequence = [0, 1]
    while len(sequence) < n:
        sequence.append(sequence[-1] + sequence[-2])
    return sequence[:n]


def is_prime(n: int) -> bool:
    """Check if a number is prime."""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True


if __name__ == "__main__":
    print("Fibonacci sequence (first 10):", fibonacci(10))
    primes = [x for x in range(2, 50) if is_prime(x)]
    print("Primes up to 50:", primes)
