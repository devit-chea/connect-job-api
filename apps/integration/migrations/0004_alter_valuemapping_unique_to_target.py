from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Flip the unique constraint on IntegrationValueMapping.

    Before: unique(field_mapping, source_value)
      → each ConnectJob value appears only once per field mapping.
      → BLOCKS many ERP values mapping to one ConnectJob value.

    After:  unique(field_mapping, target_value)
      → each ERP value appears only once per field mapping (no ambiguity).
      → ALLOWS many ERP values to share the same ConnectJob value (many-to-one).

    Example: Finance, Accounting, Tax, Auditor (ERP) → Accounting (ConnectJob)
    """

    dependencies = [
        ("integration", "0003_integration_field_value_mapping"),
    ]

    operations = [
        # Drop the old source_value uniqueness constraint
        migrations.AlterUniqueTogether(
            name="integrationvaluemapping",
            unique_together=set(),
        ),
        # Remove the named constraint added in 0003 if it exists
        migrations.RemoveConstraint(
            model_name="integrationvaluemapping",
            name="uq_integrate_value_mapping_field_source",
        ),
        # Add the new target_value uniqueness constraint
        migrations.AddConstraint(
            model_name="integrationvaluemapping",
            constraint=models.UniqueConstraint(
                fields=("field_mapping", "target_value"),
                name="uq_integrate_value_mapping_field_target",
            ),
        ),
    ]
