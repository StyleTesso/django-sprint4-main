from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView)
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.db.models import Count
from django.contrib.auth.mixins import UserPassesTestMixin

from .models import Post, Comment, Category
from .forms import PostForm, UserProfileForm, CommentForm


VALUE_POSTS_PAGINATE = 10


class OnlyAuthorMixin(UserPassesTestMixin):
    """Mixin для проверки прав автора."""

    def test_func(self):
        post = self.get_object()
        user = self.request.user
        is_author = post.author == user

        if is_author:
            return True
        return False

    def handle_no_permission(self):
        """Определяем поведение в зависимости от типа ошибки."""
        if not self.request.user.is_authenticated:
            return redirect('login')
        else:
            return redirect(reverse(
                'blog:post_detail', kwargs={'post_id': self.kwargs['post_id']}
            ))


def queryset_pattern(
        add_filter=False, category_object=None,
        add_comments=False, add_category_filter=False):
    queryset = Post.objects.select_related(
        'author',
        'category',
        'location'
    )
    """
    Функция является шаблоном для получения QuerySet,
    в зависимости от требований.
    """
    if add_filter:
        # Добавление фильтров.
        queryset = queryset.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
        if add_category_filter:
            # Добавление фильтра по категории.
            queryset = queryset.filter(category=category_object)

    if add_comments:
        # Добавления комментариев.
        queryset = queryset.annotate(
            comment_count=Count('comments')).order_by('-pub_date')
    return queryset


class PostListView(ListView):
    """Главная страница с постами."""

    paginate_by = VALUE_POSTS_PAGINATE
    template_name = 'blog/index.html'

    def get_queryset(self):
        return queryset_pattern(
            add_filter=True, add_comments=True)


class PostCreateView(LoginRequiredMixin, CreateView):
    """Создание поста."""

    model = Post
    template_name = 'blog/create.html'
    form_class = PostForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=[self.object.author.username])


class PostUpdateView(OnlyAuthorMixin, UpdateView):
    """Редактирование поста."""

    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def get_success_url(self):
        post_id = self.kwargs.get('post_id')
        return reverse('blog:post_detail', kwargs={'post_id': post_id})


class PostDetailView(DetailView):
    """Страница отдельного поста."""

    model = Post
    template_name = 'blog/detail.html'

    def get_object(self, queryset=None):
        """
        Функция гарантирует, что страницу поста смогут видеть либо его автор,
        либо любой пользователь, если пост опубликован.
        """
        post_id = self.kwargs.get('post_id')
        post_creator = get_object_or_404(Post, id=post_id)
        if post_creator.author == self.request.user:
            return post_creator
        post = get_object_or_404(
            Post, id=post_id,
            is_published=True,
            category__is_published=True)
        if post.pub_date <= timezone.now():
            return post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()
        if post is not None:
            context['form'] = CommentForm()
            context['comments'] = post.comments.all().select_related(
                'author').order_by('created_at')
        return context


class CategoryPostsView(ListView):
    """Посты по категориям."""

    model = Post
    template_name = 'blog/category.html'
    paginate_by = VALUE_POSTS_PAGINATE

    def get_object_category(self):
        """Функция получает объект категории."""
        category = get_object_or_404(
            Category, slug=self.kwargs['category_slug'], is_published=True
        )
        return category

    def get_queryset(self):
        return queryset_pattern(
            category_object=self.get_object_category(),
            add_category_filter=True,
            add_comments=True,
            add_filter=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.get_object_category()
        return context


class PostDeleteView(OnlyAuthorMixin, DeleteView):
    """Удаление поста."""

    model = Post
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')
    pk_url_kwarg = 'post_id'


class ProfileView(ListView):
    """Страница профиля."""

    model = Post
    template_name = 'blog/profile.html'
    paginate_by = VALUE_POSTS_PAGINATE

    def get_profile_object(self):
        """Получаем объект профиля."""
        profile = get_object_or_404(
            User, username=self.kwargs['username'])
        return profile

    def get_queryset(self):
        """
        Выводим фильтрацию в зависимости от того,
        является ли пользователь владельцем профиля.
        """
        if self.request.user == self.get_profile_object():
            queryset = queryset_pattern().filter(
                author=self.get_profile_object())
        else:
            queryset = queryset_pattern(
                add_comments=True,
                add_filter=True
            ).filter(author=self.get_profile_object())
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.get_profile_object()
        return context


class EditProfileView(LoginRequiredMixin, UpdateView):
    """Страница редактирования профиля."""

    model = User
    form_class = UserProfileForm
    template_name = 'blog/user.html'

    def get_success_url(self):
        """
        После успешного действия, перенаправляем пользователя
        на страницу профиля.
        """
        return reverse_lazy(
            'blog:profile', kwargs={'username': self.object.username}
        )

    def get_object(self):
        return self.request.user


class AddCommentView(LoginRequiredMixin, CreateView):
    """Комментирование записи."""

    model = Comment
    form_class = CommentForm
    template_name = 'comments.html'

    def get_success_url(self):
        """
        После успешного действия, перенаправляем пользователя
        на страницу этого поста.
        """
        post_id = self.kwargs.get('post_id')
        return reverse('blog:post_detail', kwargs={'post_id': post_id})

    def form_valid(self, form):
        post_id = self.kwargs.get('post_id')
        post = get_object_or_404(Post, id=post_id)
        form.instance.post = post
        form.instance.author = self.request.user
        return super().form_valid(form)


class EditCommentView(OnlyAuthorMixin, UpdateView):
    """Редактирование комментария."""

    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def get_object(self, queryset=None):
        comment_id = self.kwargs.get('comment_id')
        post_id = self.kwargs.get('post_id')
        return get_object_or_404(Comment, id=comment_id, post_id=post_id)

    def get_success_url(self):
        """
        После успешного действия, перенаправляем пользователя
        на страницу этого поста.
        """
        post_id = self.kwargs.get('post_id')
        return reverse('blog:post_detail', kwargs={'post_id': post_id})


class DeleteCommentView(OnlyAuthorMixin, DeleteView):
    """Удаление комментария."""

    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_object(self, queryset=None):
        comment_id = self.kwargs.get('comment_id')
        post_id = self.kwargs.get('post_id')
        return get_object_or_404(Comment, id=comment_id, post_id=post_id)

    def get_success_url(self):
        """
        После успешного действия, перенаправляем пользователя
        на страницу этого поста.
        """
        post_id = self.kwargs.get('post_id')
        return reverse_lazy('blog:post_detail', kwargs={'post_id': post_id})
