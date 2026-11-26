from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Post

POSTS_PER_PAGE = 10
User = get_user_model()


def public_post_conditions():
    return Q(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    )


def display_category(post):
    if post.category_id is None:
        # The supplied templates need a title and slug even after deletion.
        post.category = Category(
            title='Без категории', slug='category-removed',
        )


def post_list(posts, request):
    posts = posts.select_related('author', 'category', 'location').annotate(
        comment_count=Count('comments'),
    ).order_by('-pub_date', '-pk')
    page = Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))
    for post in page:
        display_category(post)
    return page


def visible_post(user, post_id):
    conditions = public_post_conditions()
    if user.is_authenticated:
        conditions |= Q(author=user)
    return get_object_or_404(
        Post.objects.select_related('author', 'category', 'location'),
        conditions,
        pk=post_id,
    )


def index(request):
    posts = Post.objects.filter(public_post_conditions())
    return render(request, 'blog/index.html', {
        'page_obj': post_list(posts, request),
    })


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True,
    )
    posts = category.posts.filter(public_post_conditions())
    return render(request, 'blog/category.html', {
        'category': category,
        'page_obj': post_list(posts, request),
    })


def profile(request, username):
    owner = get_object_or_404(User, username=username)
    posts = owner.posts.all()
    if request.user != owner:
        posts = posts.filter(public_post_conditions())
    return render(request, 'blog/profile.html', {
        'profile': owner,
        'page_obj': post_list(posts, request),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request):
    form = ProfileForm(
        request.POST if request.method == 'POST' else None,
        instance=request.user,
    )
    if form.is_valid():
        user = form.save()
        return redirect('blog:profile', username=user.username)
    return render(request, 'blog/user.html', {'form': form})


def render_post(request, post, form):
    display_category(post)
    return render(request, 'blog/detail.html', {
        'post': post,
        'form': form,
        'comments': post.comments.select_related('author'),
    })


def post_detail(request, post_id):
    return render_post(request, visible_post(request.user, post_id),
                       CommentForm())


@login_required
@require_http_methods(['GET', 'POST'])
def create_post(request):
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=post,
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:index')
    return render(request, 'blog/create.html', {
        'form': PostForm(instance=post),
    })


@login_required
@require_POST
def add_comment(request, post_id):
    post = visible_post(request.user, post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render_post(request, post, form)


@login_required
@require_http_methods(['GET', 'POST'])
def edit_comment(request, post_id, comment_id):
    post = visible_post(request.user, post_id)
    comment = get_object_or_404(post.comments, pk=comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    form = CommentForm(
        request.POST if request.method == 'POST' else None,
        instance=comment,
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {
        'form': form,
        'comment': comment,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def delete_comment(request, post_id, comment_id):
    post = visible_post(request.user, post_id)
    comment = get_object_or_404(post.comments, pk=comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
