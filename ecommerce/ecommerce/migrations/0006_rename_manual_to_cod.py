# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ecommerce", "0005_checkout_payment_settings"),
    ]

    operations = [
        migrations.RenameField(
            model_name="checkoutpaymentsettings",
            old_name="allow_manual_complete",
            new_name="allow_cod_complete",
        ),
        migrations.AlterField(
            model_name="checkoutpaymentsettings",
            name="allow_cod_complete",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, customers can place orders with Cash on Delivery via "
                    "POST /checkouts/{id}/complete/ (order financial_status stays pending)."
                ),
            ),
        ),
    ]
