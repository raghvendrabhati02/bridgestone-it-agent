import sys
import os
import unittest
import time

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.retry_helper import with_retry

class TestRetryEngine(unittest.TestCase):
    def test_retry_attempts_and_backoff(self):
        """Verifies that the @with_retry decorator retries the exact number of times on failures."""
        attempts = 0

        @with_retry(retries=3, backoff_factor=1.5, jitter=False)
        def failing_function():
            nonlocal attempts
            attempts += 1
            raise ValueError("Transient error")

        start_time = time.time()
        with self.assertRaises(ValueError):
            failing_function()
        end_time = time.time()

        # The function should run exactly 3 times
        self.assertEqual(attempts, 3)
        
        # Expected delays:
        # Attempt 1: fails immediately, sleeps 1.0s
        # Attempt 2: fails immediately, sleeps 1.5s
        # Attempt 3: fails immediately, raises error
        # Total sleep time should be around 2.5 seconds
        duration = end_time - start_time
        self.assertTrue(duration >= 2.4, f"Duration was only {duration:.2f}s, expected at least 2.4s")
        print(f"[OK] Retry engine verified: {attempts} attempts executed in {duration:.2f}s with exponential backoff.")

if __name__ == "__main__":
    unittest.main()
