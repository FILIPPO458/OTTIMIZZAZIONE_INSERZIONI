from urllib.parse import unquote

code_raw = "v%5E1.1%23i%5E1%23f%5E0%23I%5E3%23r%5E1%23p%5E3%23t%5EUl41XzA6QTBBNjM0RjE5OTREQUVDOURENERBNUY1NUEzM0JDMkFfMF8xI0VeMjYw"

code_decoded = unquote(code_raw)
print(code_decoded)
