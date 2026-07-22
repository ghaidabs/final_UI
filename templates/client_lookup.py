from templates.spoken_format import spoken_phone_number

def build_client_spoken(client: dict, language: str = "fr") -> str:
    full_name = f"{client['first_name']} {client['last_name']}"
    phone_spoken = spoken_phone_number(client["phone"], language=language)

    if language == "en":
        return (
            f"I found {full_name}. "
            f"You can reach them at {phone_spoken}, "
            f"located at {client['address']}."
        )

    return (
        f"J'ai trouvé {full_name}. "
        f"Vous pouvez le joindre au {phone_spoken}, "
        f"se trouvant à {client['address']}."
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


def build_client_display(client: dict, language: str = "fr") -> str:
    full_name = f"{client['first_name']} {client['last_name']}"
    phone = client["phone"]
    
    if language == "en":
        return f"Client {full_name} is found. "
    return f"Client {full_name} est trouvé. "


def build_client_list_display(clients: list[dict], language: str = "fr") -> str:
    if not clients:
        return "No clients found matching that name." if language == "en" else "Aucun client trouvé pour ce nom."
    
    if len(clients) == 1:
        return build_client_display(clients[0], language=language)
    
    names = ", ".join(f"{c['first_name']} {c['last_name']}" for c in clients)
   
    if language == "en":
        return f"Found {len(clients)} clients: {names}. Which one did you mean?"

    return f"{len(clients)} clients trouvés : {names}."