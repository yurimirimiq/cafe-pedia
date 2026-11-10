from django.core.management.base import BaseCommand

from api import recommend


class Command(BaseCommand):
    help = '예상 별점이 실제 별점과 얼마나 다른지 (leave-one-out RMSE) 방식별로 비교한다'

    def handle(self, *args, **options):
        result = recommend.evaluate(recommend.rating_table())
        if not result:
            self.stdout.write(f'평가가 {recommend.MIN_REVIEWS + 1}개 이상인 사람이 없어서 잴 수 없어요')
        for name, (rmse, count) in result.items():
            self.stdout.write(f'{name:>8}  RMSE {rmse:.3f}  ({count}개)')
