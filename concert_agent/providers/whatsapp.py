import httpx

from concert_agent.config import Settings


class WhatsAppProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_text(self, to: str, body: str) -> str | None:
        if self.settings.dry_run:
            return f"dry-run:{to}"
        if not self.settings.whatsapp_access_token or not self.settings.whatsapp_phone_number_id:
            raise RuntimeError("WhatsApp credentials are not configured")

        url = (
            f"https://graph.facebook.com/{self.settings.whatsapp_api_version}/"
            f"{self.settings.whatsapp_phone_number_id}/messages"
        )
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.settings.whatsapp_access_token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": True, "body": body},
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        messages = data.get("messages", [])
        return messages[0].get("id") if messages else None
