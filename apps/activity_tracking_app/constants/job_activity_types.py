from django.db import models


class ActivityTrackingTypes(models.TextChoices):
    APPLY = "apply", "Apply"
    SAVE = "save", "Save"
    VIEW = "view", "View"
    UNSAVE = "unsave", "Unsave"
    SHARE = "share", "Share"
    REPORT = "report", "Report"
    BOOKMARK = "bookmark", "Bookmark"
