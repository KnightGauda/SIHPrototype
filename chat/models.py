from django.db import models

class QueryLog(models.Model):
    query = models.TextField()
    response_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.query[:80]} - {self.created_at.isoformat()}"
