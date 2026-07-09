def build_client_spoken(client: dict, language: str = "fr") -> str:
    full_name = f"{client['first_name']} {client['last_name']}"

    if language == "en":
        return (
            f"Found {full_name}. "
            f"Phone: {client['phone']}. "
            f"Address: {client['address']}."
        )

    return (
        f"J'ai trouvé {full_name}. "
        f"Téléphone : {client['phone']}. "
        f"Adresse : {client['address']}."
    )


def build_client_list_spoken(clients: list[dict], language: str = "fr") -> str:
    if not clients:
        return "No clients found matching that name." if language == "en" else "Aucun client trouvé pour ce nom."

    if len(clients) == 1:
        return build_client_spoken(clients[0], language=language)

    names = ", ".join(f"{c['first_name']} {c['last_name']}" for c in clients)

    if language == "en":
        return f"I found {len(clients)} clients: {names}. Which one did you mean?"

    return f"J'ai trouvé {len(clients)} clients : {names}. Lequel vouliez-vous dire ?"