class ConnectorStatus:
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

    CHOICES = (
        (ACTIVE, "Active"),
        (DISCONNECTED, "Disconnected"),
        (REVOKED, "Revoked"),
        (SUSPENDED, "Suspended"),
    )
