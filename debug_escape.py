text = "Don't worry"
escaped = text
escaped = escaped.replace("'", "'\\''")
print(f"Original: {text}")
print(f"Escaped: {escaped}")
print(f"Contains: {'\\' in escaped}")
