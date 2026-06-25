def validate_product_name(name: str) -> None:
    if not name or not name.strip():
        raise ValueError("Название продукта не может быть пустым")
