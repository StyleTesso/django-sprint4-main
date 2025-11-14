from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.db.models import Count

from .models import Category


class OnlyAuthorMixin(UserPassesTestMixin):

    def test_func(self):
        object = self.get_object()
        return object.author == self.request.user


def get_object_category(category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True)
    return category


def query(qs, filters: dict, need_annotate: bool = False,
          order_by: str = '-pub_date'):
    queryset = qs.filter(**filters).select_related(
        'author', 'category', 'location')
    if need_annotate:
        queryset = queryset.annotate(comment_count=Count('comments'))
    return queryset.order_by(order_by)
