from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ecommerce", "0007_alter_checkoutpaymentsettings_allow_cod_complete_and_more"),
        ("logistics", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fulfillment",
            name="logistics_shipment",
            field=models.ForeignKey(
                blank=True,
                help_text="Logistics pipeline shipment; status and tracking sync from here.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ecommerce_fulfillments",
                to="logistics.shipment",
            ),
        ),
    ]
