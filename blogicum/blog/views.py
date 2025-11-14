from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView)
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.core.exceptions import PermissionDenied

from .models import Post, Comment
from .forms import PostForm, UserProfileForm, CommentForm
from .utils import OnlyAuthorMixin, get_object_category, query

VALUE_POSTS_PAGINATE = 10


class PostListView(ListView):
    """Главная страница с постами."""

    paginate_by = VALUE_POSTS_PAGINATE
    template_name = 'blog/index.html'

    def get_queryset(self):
        queryset = query(
            Post.objects,
            {
                'is_published': True,
                'pub_date__lte': timezone.now(),
                'category__is_published': True
            },
            need_annotate=True
        )
        return queryset


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

    def dispatch(self, request, *args, **kwargs):
        # Проверка на авторизацию.
        if not self.test_func():
            return redirect(reverse(
                'blog:post_detail', kwargs={'post_id': self.kwargs['post_id']}
            ))
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail', kwargs={'post_id': self.object.pk})


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
        post = get_object_or_404(Post, id=post_id)
        if (
            post.author == self.request.user
            or (post.is_published and post.category.is_published
                and post.pub_date <= timezone.now())
        ):
            return post
        raise Http404('Страница не найдена')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()
        context['form'] = CommentForm()
        context['comments'] = post.comments.all().select_related(
            'author').order_by('created_at')
        return context


class CategoryPostsView(ListView):
    """Посты по категориям."""

    model = Post
    template_name = 'blog/category.html'
    paginate_by = VALUE_POSTS_PAGINATE

    def get_queryset(self):
        category_slug = self.kwargs['category_slug']
        queryset = query(
            Post.objects,
            {
                'is_published': True,
                'pub_date__lte': timezone.now(),
                'category__is_published': True,
                'category__slug': category_slug

            },
            need_annotate=True
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = get_object_category(self.kwargs['category_slug'])
        return context


class PostDeleteView(OnlyAuthorMixin, DeleteView):
    """Удаление поста."""

    model = Post
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        # Проверка на авторизацию.
        access = self.get_object()
        if not request.user.is_authenticated:
            return redirect('login')
        if access.author != request.user:
            raise PermissionDenied(
                'Недостаточно прав для просмотра этой страницы')
        return super().dispatch(request, *args, **kwargs)


class ProfileView(ListView):
    """Страница профиля."""

    model = Post
    template_name = 'blog/profile.html'
    paginate_by = VALUE_POSTS_PAGINATE

    def get_queryset(self):
        username = self.kwargs['username']
        profile = get_object_or_404(User, username=username)
        if self.request.user == profile:
            queryset = query(
                Post.objects,
                {
                    'author': profile,
                },
                need_annotate=True
            )
            return queryset
        else:
            queryset = query(
                Post.objects,
                {
                    'author': profile,
                    'is_published': True,
                    'pub_date__lte': timezone.now(),
                    'category__is_published': True
                },
                need_annotate=True
            )
            return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_object_or_404(
            User, username=self.kwargs['username'])
        return context


class EditProfileView(LoginRequiredMixin, UpdateView):
    """Страница редактирования профиля."""

    model = User
    form_class = UserProfileForm
    template_name = 'blog/user.html'

    def get_success_url(self):
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
    success_url = reverse_lazy('blog:index')

    def get_object(self, queryset=None):
        comment_id = self.kwargs.get('comment_id')
        post_id = self.kwargs.get('post_id')
        return get_object_or_404(Comment, id=comment_id, post_id=post_id)

    def dispatch(self, request, *args, **kwargs):
        # Проверка на авторизацию.
        access = self.get_object()
        if not request.user.is_authenticated:
            return redirect('login')
        if access.author != request.user:
            raise PermissionDenied(
                'Недостаточно прав для просмотра этой страницы')
        return super().dispatch(request, *args, **kwargs)


class DeleteCommentView(OnlyAuthorMixin, DeleteView):
    """Удаление комментария."""

    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_object(self, queryset=None):
        comment_id = self.kwargs.get('comment_id')
        post_id = self.kwargs.get('post_id')
        return get_object_or_404(Comment, id=comment_id, post_id=post_id)

    def dispatch(self, request, *args, **kwargs):
        # Проверка на авторизацию.
        access = self.get_object()
        if not request.user.is_authenticated:
            return redirect('login')
        if access.author != request.user:
            raise PermissionDenied(
                'Недостаточно прав для просмотра этой страницы')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        post_id = self.kwargs.get('post_id')
        return reverse_lazy('blog:post_detail', kwargs={'post_id': post_id})
