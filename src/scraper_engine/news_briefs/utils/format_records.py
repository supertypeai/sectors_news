def format_records(records: list[dict], fields: list[tuple[str, str]]) -> str:
    formatted_records = []

    for record in records:
        formatted_fields = []

        for field_name, label in fields:
            value = record.get(field_name)

            if isinstance(value, list):
                value = ", ".join(
                    str(item)
                    for item in value
                )
            elif value is None:
                value = ""

            formatted_fields.append(f"{label}: {value}")

        formatted_records.append("\n".join(formatted_fields))

    return "\n\n".join(formatted_records)
