from rest_framework.routers import DefaultRouter

from apps.activity_tracking_app.views.views import (
    JobPostUserActivityCountView,
    SavedJobViewSet,
    AppliedJobViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register(
    r"activity_count", JobPostUserActivityCountView, basename="activity_count"
)
router.register("activity/jobs/saved", SavedJobViewSet, basename="saved-jobs")
router.register("activity/jobs/applied", AppliedJobViewSet, basename="applied-jobs")

urlpatterns = [
    *router.urls,
]
