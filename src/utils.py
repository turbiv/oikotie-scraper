def get_item(self, index):
    try:
        return self[index]
    except Exception:
        return None