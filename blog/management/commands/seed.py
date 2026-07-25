from itertools import batched
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from blog.models import Comment, Post, Tag, User

NUM_USERS = 1000
NUM_TAGS = 50
NUM_POSTS = 100_000
NUM_COMMENTS = 500_000
TAGS_PER_POST_AVG = 3
TITLE_POOL_SIZE = 50_000
BODY_POOL_SIZE = 50_000
COMMENT_POOL_SIZE = 100_000
BATCH = 10_000


class Command(BaseCommand):
    help = "Seed the database with users, tags, posts, and comments."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Seed even if data exists")

    def handle(self, *args, **opts):
        if User.objects.exists() and not opts["force"]:
            self.stdout.write("Database already has users; pass --force to seed anyway.")
            return

        fake = Faker()
        Faker.seed(42)
        random.seed(42)

        now = timezone.now()
        three_years_ago = now - timedelta(days=365 * 3)
        recency_cutoff = now - timedelta(days=180)

        total_ms_3yr = int((now - three_years_ago).total_seconds() * 1000)
        total_ms_recent = int((now - recency_cutoff).total_seconds() * 1000)

        self.stdout.write("Seeding users...")
        users_generator = (
            User(
                username=f"user{i:05d}",
                email=f"user{i:05d}@example.com",
                display_name=fake.name(),
                bio=fake.text(max_nb_chars=200) if i % 4 == 0 else "",
                created_at=_rand_time_3yr(three_years_ago, total_ms_3yr),
            )
            for i in range(NUM_USERS)
        )
        for chunk in batched(users_generator, BATCH):
            User.objects.bulk_create(chunk)

        user_ids = list(User.objects.values_list("id", flat=True))
        author_weights = _power_law_weights(len(user_ids), top_n=10, top_share=0.3)

        self.stdout.write("Seeding tags...")
        hot_slugs = ["python", "django", "postgres", "devops", "sre"]
        tag_generator = (
            Tag(
                name=s.title() if i < len(hot_slugs) else (word := fake.unique.word()).title(),
                slug=s if i < len(hot_slugs) else slugify(word),
                created_at=now,
            )
            for i, s in enumerate(hot_slugs + [None] * (NUM_TAGS - len(hot_slugs)))
        )
        for chunk in batched(tag_generator, BATCH):
            Tag.objects.bulk_create(chunk)

        tags = list(Tag.objects.values_list("id", "slug"))
        hot_tag_ids = [t[0] for t in tags if t[1] in hot_slugs]
        cold_tag_ids = [t[0] for t in tags if t[1] not in hot_slugs]

        self.stdout.write(f"Seeding {NUM_POSTS} posts...")
        title_pool = [fake.sentence(nb_words=8).rstrip(".") for _ in range(TITLE_POOL_SIZE)]
        body_pool = [fake.text(max_nb_chars=600) for _ in range(BODY_POOL_SIZE)]

        post_authors = random.choices(user_ids, weights=author_weights, k=NUM_POSTS)
        post_titles = random.choices(title_pool, k=NUM_POSTS)
        post_bodies = random.choices(body_pool, k=NUM_POSTS)

        posts_generator = (
            Post(
                author_id=post_authors[i],
                title=post_titles[i],
                body=post_bodies[i],
                is_published=random.random() < 0.9,
                view_count=random.randint(0, 5000),
                created_at=(
                    _rand_time_recent(recency_cutoff, total_ms_recent)
                    if random.random() < 0.5
                    else _rand_time_3yr(three_years_ago, total_ms_3yr)
                ),
            )
            for i in range(NUM_POSTS)
        )
        for chunk in batched(posts_generator, BATCH):
            Post.objects.bulk_create(chunk)

        post_data = list(Post.objects.values_list("id", "created_at"))
        post_ids = [p[0] for p in post_data]

        self.stdout.write("Attaching tags to posts...")
        through = Post.tags.through

        def m2m_generator():
            for pid in post_ids:
                n_tags = max(1, int(random.gauss(TAGS_PER_POST_AVG, 1)))
                chosen = set()
                for _ in range(n_tags):
                    if random.random() < 0.4 and hot_tag_ids:
                        chosen.add(random.choice(hot_tag_ids))
                    else:
                        chosen.add(random.choice(cold_tag_ids))
                for tid in chosen:
                    yield through(post_id=pid, tag_id=tid)

        for chunk in batched(m2m_generator(), BATCH):
            through.objects.bulk_create(chunk, ignore_conflicts=True)

        self.stdout.write(f"Seeding {NUM_COMMENTS} comments...")
        comment_post_weights = _long_tail_weights(len(post_data), top_pct=0.01, top_share=0.5)

        comment_text_pool = [
            f"{fake.sentence(nb_words=5).rstrip('.')}. {fake.sentence(nb_words=10)}"
            for _ in range(COMMENT_POOL_SIZE)
        ]

        chosen_posts = random.choices(post_data, weights=comment_post_weights, k=NUM_COMMENTS)
        comment_authors = random.choices(user_ids, weights=author_weights, k=NUM_COMMENTS)
        comment_bodies = random.choices(comment_text_pool, k=NUM_COMMENTS)

        comment_offsets = [
            random.randint(0, max_ms) if (max_ms := int((now - p[1]).total_seconds() * 1000)) > 0 else 0
            for p in chosen_posts
        ]

        comments_generator = (
            Comment(
                post_id=chosen_posts[i][0],
                author_id=comment_authors[i],
                body=comment_bodies[i],
                created_at=chosen_posts[i][1] + timedelta(milliseconds=comment_offsets[i]),
            )
            for i in range(NUM_COMMENTS)
        )
        for chunk in batched(comments_generator, BATCH):
            Comment.objects.bulk_create(chunk)

        self.stdout.write(self.style.SUCCESS("Done."))


def _rand_time_3yr(three_years_ago, total_ms_3yr):
    return three_years_ago + timedelta(milliseconds=random.randint(0, total_ms_3yr))


def _rand_time_recent(recency_cutoff, total_ms_recent):
    return recency_cutoff + timedelta(milliseconds=random.randint(0, total_ms_recent))


def _power_law_weights(n, top_n, top_share):
    weights = [1.0] * n
    bonus = (top_share * n) / max(top_n, 1)
    for i in range(min(top_n, n)):
        weights[i] = 1.0 + bonus
    return weights


def _long_tail_weights(n, top_pct, top_share):
    weights = [1.0] * n
    top_n = max(1, int(n * top_pct))
    bonus = (top_share * n) / top_n
    for i in range(top_n):
        weights[i] = 1.0 + bonus
    return weights
