import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from delegates.models import Delegate, DelegateTransaction, DelegateTransactionType, TransactionDirection
from merchants.models import Merchant, MerchantPayment, PaymentDirection
from orders.models import Order, OrderStatus


def _rand_phone() -> str:
    # Simple Egyptian-like mobile numbers for demo
    prefixes = ["010", "011", "012", "015"]
    return random.choice(prefixes) + "".join(str(random.randint(0, 9)) for _ in range(8))


def _rand_address(i: int) -> str:
    cities = ["القاهرة", "الجيزة", "الإسكندرية", "بورسعيد", "السويس", "المنصورة", "طنطا", "الزقازيق"]
    areas = ["وسط البلد", "فيصل", "الهرم", "سيدي جابر", "العباسية", "مدينة نصر", "الزمالك", "المعادي"]
    return f"{random.choice(cities)} - {random.choice(areas)} - شارع {i}"


class Command(BaseCommand):
    help = "Seed demo data (merchants, delegates, orders)"

    def add_arguments(self, parser):
        parser.add_argument("--merchants", type=int, default=20)
        parser.add_argument("--delegates", type=int, default=7)
        parser.add_argument("--orders", type=int, default=50)
        parser.add_argument("--reset", action="store_true", help="Delete existing data in merchants/delegates/orders first")
        parser.add_argument("--force", action="store_true", help="Skip confirmation when using --reset")

    def handle(self, *args, **options):
        target_merchants = int(options["merchants"])
        target_delegates = int(options["delegates"])
        target_orders = int(options["orders"])
        reset = bool(options["reset"])
        force = bool(options["force"])

        if reset and not force:
            self.stdout.write(self.style.WARNING("تحذير: ده هيمسح كل بيانات التجار/المناديب/الأوردرات والحركات."))
            confirm = input("اكتب YES للمتابعة: ").strip()
            if confirm != "YES":
                self.stdout.write(self.style.ERROR("تم الإلغاء."))
                return

        with transaction.atomic():
            if reset:
                DelegateTransaction.objects.all().delete()
                MerchantPayment.objects.all().delete()
                Order.objects.all().delete()
                Merchant.objects.all().delete()
                Delegate.objects.all().delete()

            merchants = list(Merchant.objects.all())
            delegates = list(Delegate.objects.all())

            merchant_start = len(merchants) + 1
            while len(merchants) < target_merchants:
                i = merchant_start
                merchant_start += 1
                m = Merchant.objects.create(
                    name=f"تاجر {i:03d}",
                    phone=_rand_phone(),
                    address=_rand_address(i),
                    brand_name=f"Brand {i:03d}",
                    is_active=True,
                )
                merchants.append(m)

            delegate_start = len(delegates) + 1
            while len(delegates) < target_delegates:
                i = delegate_start
                delegate_start += 1
                d = Delegate.objects.create(
                    name=f"مندوب {i:02d}",
                    phone=_rand_phone(),
                    commission_rate=Decimal("0.75"),
                    fixed_deduction=Decimal("0"),
                    is_active=True,
                )
                delegates.append(d)

            existing_waybills = set(Order.objects.values_list("waybill_number", flat=True))
            base_num = random.randint(100000, 900000)

            def new_waybill() -> str:
                nonlocal base_num
                while True:
                    base_num += 1
                    wb = f"BRB{base_num}"
                    if wb not in existing_waybills:
                        existing_waybills.add(wb)
                        return wb

            orders_count = Order.objects.count()
            while orders_count < target_orders:
                merchant = random.choice(merchants)
                delegate = random.choice(delegates)

                status = random.choices(
                    [OrderStatus.DELIVERED, OrderStatus.IN_TRANSIT, OrderStatus.ACCOUNTED],
                    weights=[0.4, 0.4, 0.2],
                    k=1,
                )[0]

                order_date = timezone.localdate() - timedelta(days=random.randint(0, 14))
                shipping_price = Decimal(str(random.choice([35, 40, 45, 50, 60, 70, 80])))
                product_price = Decimal(str(random.randint(150, 2500)))

                Order.objects.create(
                    waybill_number=new_waybill(),
                    order_date=order_date,
                    merchant=merchant,
                    delegate=delegate,
                    customer_name=f"عميل {random.randint(1, 999)}",
                    customer_phone=_rand_phone(),
                    customer_address=_rand_address(random.randint(1, 500)),
                    shipping_price=shipping_price,
                    product_price=product_price,
                    status=status,
                    notes="",
                )
                orders_count += 1

            # Add a few random payments and transactions for better demo UI
            for merchant in random.sample(merchants, k=min(5, len(merchants))):
                MerchantPayment.objects.create(
                    merchant=merchant,
                    payment_date=timezone.localdate() - timedelta(days=random.randint(0, 7)),
                    direction=PaymentDirection.IN,
                    amount=Decimal(str(random.randint(500, 5000))),
                    notes="دفعة تجريبية",
                )

            for delegate in random.sample(delegates, k=min(3, len(delegates))):
                DelegateTransaction.objects.create(
                    delegate=delegate,
                    transaction_date=timezone.localdate(),
                    tx_type=DelegateTransactionType.ADVANCE,
                    direction=TransactionDirection.IN,
                    amount=Decimal("400"),
                    notes="عهدة تجريبية",
                )
                DelegateTransaction.objects.create(
                    delegate=delegate,
                    transaction_date=timezone.localdate(),
                    tx_type=DelegateTransactionType.DEPOSIT,
                    direction=TransactionDirection.OUT,
                    amount=Decimal("300"),
                    notes="توريد تجريبي",
                )

        self.stdout.write(self.style.SUCCESS("تم تجهيز داتا تجريبية بنجاح."))
