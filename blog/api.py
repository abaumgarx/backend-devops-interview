from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.pagination import CursorPagination, paginate

from blog.models import Comment, Post, Tag, User
from blog.schemas import (
    CommentCreateIn,
    CommentCreateOut,
    PostCreateIn,
    PostCreateOut,
    PostDetailOut,
    PostListOut,
    UserDetailOut,
)

router = Router()


@router.get("/posts", response=list[PostListOut])
@paginate(CursorPagination, ordering=("-created_at", "-id"), page_size=20)
def list_posts(request):
    return (
        Post.objects.filter(is_published=True)
        .select_related("author")
        .prefetch_related("tags")
    )


@router.get("/posts/search", response=list[PostListOut])
@paginate(CursorPagination, ordering=("-created_at", "-id"), page_size=20)
def search_posts(request, q: str):
    return (
        Post.objects.filter(is_published=True)
        .filter(Q(title__icontains=q) | Q(body__icontains=q))
        .select_related("author")
        .prefetch_related("tags")
    )


@router.get("/posts/by-tag/{slug}", response=list[PostListOut])
@paginate(CursorPagination, ordering=("-created_at", "-id"), page_size=20)
def posts_by_tag(request, slug: str):
    return (
        Post.objects.filter(is_published=True, tags__slug=slug)
        .select_related("author")
        .prefetch_related("tags")
    )


@router.get("/posts/{post_id}", response=PostDetailOut)
def get_post(request, post_id: int):
    post = get_object_or_404(
        Post.objects.select_related("author").prefetch_related(
            "tags", "comments__author"
        ),
        id=post_id,
    )
    Post.objects.filter(id=post_id).update(view_count=F("view_count") + 1)
    post.view_count += 1
    return post


@transaction.atomic
@router.post("/posts", response=PostCreateOut)
def create_post(request, payload: PostCreateIn):
    author = get_object_or_404(User, id=payload.author_id)
    post = Post.objects.create(
        author=author,
        title=payload.title,
        body=payload.body,
    )
    if payload.tag_slugs:
        post.tags.set(Tag.objects.filter(slug__in=payload.tag_slugs))
    return post


@router.post("/posts/{post_id}/comments", response=CommentCreateOut)
def create_comment(request, post_id: int, payload: CommentCreateIn):
    post = get_object_or_404(Post, id=post_id)
    author = get_object_or_404(User, id=payload.author_id)
    return Comment.objects.create(post=post, author=author, body=payload.body)


@router.get("/users/find", response=UserDetailOut)
def find_user_by_email(request, email: str):
    return get_object_or_404(
        User.objects.annotate(
            post_count=Count("posts", distinct=True),
            comment_count=Count("comments", distinct=True),
        ),
        email=email,
    )


@router.get("/users/{user_id}", response=UserDetailOut)
def get_user(request, user_id: int):
    return get_object_or_404(
        User.objects.annotate(
            post_count=Count("posts", distinct=True),
            comment_count=Count("comments", distinct=True),
        ),
        id=user_id,
    )
