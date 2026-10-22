from cms.models import CMSPlugin
from django.db import models
from django.urls import reverse
from django.utils import timezone
from filer.fields.image import FilerImageField

BACKGROUNDS = [
    ("white", "White"),
    ("pale", "Pale blue"),
    ("sky", "Light blue"),
    ("blue", "Royal blue"),
    ("navy", "Navy"),
    ("bright", "Bright blue"),
]

ICONS = [
    ("", "None"),
    ("home", "Home"),
    ("star", "Star"),
    ("briefcase", "Briefcase"),
    ("people", "People"),
    ("shield", "Shield"),
    ("health", "Health"),
    ("hardhat", "Hard hat"),
    ("car", "Car"),
]


def parse_links(text):
    """'Label|/url/' per line -> [(label, url)]. A line without a pipe links nowhere."""
    links = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        label, _, url = line.partition("|")
        links.append((label.strip(), url.strip() or "#"))
    return links


class ImageMixin(models.Model):
    image = FilerImageField(null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    image_url = models.CharField("Image URL (if not uploaded)", max_length=500, blank=True)
    image_alt = models.CharField("Image description", max_length=255, blank=True)

    class Meta:
        abstract = True

    @property
    def image_src(self):
        if self.image_id:
            return self.image.url
        return self.image_url


class Section(CMSPlugin):
    background = models.CharField(max_length=10, choices=BACKGROUNDS, default="white")
    eyebrow = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=255, blank=True)
    intro = models.TextField(blank=True)
    link_text = models.CharField(max_length=120, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    anchor = models.SlugField("Anchor ID", blank=True)
    compact = models.BooleanField("Less vertical padding", default=False)

    def __str__(self):
        return self.heading or self.eyebrow or "Section"


class Hero(ImageMixin, CMSPlugin):
    STYLES = [("home", "Homepage, with quote card"), ("page", "Page, with photo")]
    style = models.CharField(max_length=10, choices=STYLES, default="page")
    badge = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=255)
    subheading = models.TextField(blank=True)
    primary_text = models.CharField(max_length=80, blank=True)
    primary_url = models.CharField(max_length=500, blank=True)
    secondary_text = models.CharField(max_length=80, blank=True)
    secondary_url = models.CharField(max_length=500, blank=True)
    checklist = models.TextField("Check marks (one per line)", blank=True)

    def __str__(self):
        return self.heading

    @property
    def checklist_items(self):
        return [line.strip() for line in self.checklist.splitlines() if line.strip()]


class Stat(CMSPlugin):
    value = models.CharField(max_length=40)
    label = models.CharField(max_length=120)

    def __str__(self):
        return f"{self.value} {self.label}"


class CardGrid(CMSPlugin):
    STYLES = [
        ("service", "Service cards (blue top edge)"),
        ("program", "Program cards (photo, dark)"),
        ("tile", "Link tiles"),
        ("plain", "Bordered cards"),
        ("soft", "Soft blue cards"),
    ]
    columns = models.PositiveSmallIntegerField(choices=[(2, "2"), (3, "3"), (4, "4"), (6, "6")], default=3)
    style = models.CharField(max_length=10, choices=STYLES, default="plain")

    def __str__(self):
        return f"{self.get_style_display()}, {self.columns} columns"


class Card(ImageMixin, CMSPlugin):
    icon = models.CharField(max_length=20, choices=ICONS, blank=True)
    badge = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    links = models.TextField("Links (Label|URL, one per line)", blank=True)
    link_text = models.CharField(max_length=120, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    highlight = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    @property
    def link_list(self):
        return parse_links(self.links)


class Split(ImageMixin, CMSPlugin):
    eyebrow = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    button_text = models.CharField(max_length=80, blank=True)
    button_url = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.heading


class TeamStrip(CMSPlugin):
    heading = models.CharField(max_length=255, default="Meet the people behind your policy")
    link_text = models.CharField(max_length=120, default="Meet the full team →")
    link_url = models.CharField(max_length=500, default="/our-team/")
    count = models.PositiveSmallIntegerField(default=6)
    show_all = models.BooleanField("Show every team member", default=False)

    def __str__(self):
        return self.heading


class Testimonial(CMSPlugin):
    quote = models.TextField()
    attribution = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.quote[:60]


class LatestPosts(CMSPlugin):
    heading = models.CharField(max_length=255, default="From the blog")
    count = models.PositiveSmallIntegerField(default=4)

    def __str__(self):
        return self.heading


class CTABand(CMSPlugin):
    heading = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    primary_text = models.CharField(max_length=80, blank=True)
    primary_url = models.CharField(max_length=500, blank=True)
    secondary_text = models.CharField(max_length=80, blank=True)
    secondary_url = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.heading


class Callout(CMSPlugin):
    eyebrow = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    button_text = models.CharField(max_length=80, blank=True)
    button_url = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.heading


class PillList(CMSPlugin):
    heading = models.CharField(max_length=255, blank=True)
    intro = models.TextField(blank=True)
    items = models.TextField("Items (Label|URL, one per line)")

    def __str__(self):
        return self.heading or "Pill list"

    @property
    def item_list(self):
        return parse_links(self.items)


class FAQItem(CMSPlugin):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    open = models.BooleanField("Open by default", default=False)

    def __str__(self):
        return self.question


class QuoteForm(CMSPlugin):
    FORM_TYPES = [
        ("general", "General quote"),
        ("contractor", "Contractor quote"),
        ("hospital", "Hospital inquiry"),
        ("benefits", "Group benefits quote"),
        ("contact", "Contact message"),
    ]
    form_type = models.CharField(max_length=20, choices=FORM_TYPES, default="general")
    heading = models.CharField(max_length=255, default="Get a quote")
    intro = models.TextField(blank=True, default="A licensed agent will follow up within one business day.")
    button_text = models.CharField(max_length=80, default="Submit")
    dark = models.BooleanField("Navy background", default=True)

    def __str__(self):
        return f"{self.get_form_type_display()}: {self.heading}"


# Content models -------------------------------------------------------------


class TeamMember(models.Model):
    name = models.CharField(max_length=120)
    title = models.CharField(max_length=160, blank=True)
    photo = FilerImageField(null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    photo_url = models.CharField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=100)
    featured = models.BooleanField("Show on homepage", default=False)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @property
    def photo_src(self):
        return self.photo.url if self.photo_id else self.photo_url


class BlogCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "blog categories"

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=200, unique=True)
    published = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField(blank=True)
    featured_image_url = models.CharField(max_length=500, blank=True)
    categories = models.ManyToManyField(BlogCategory, blank=True, related_name="posts")
    seo_title = models.CharField(max_length=300, blank=True)
    seo_description = models.TextField(blank=True)
    wp_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-published"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/{self.slug}/"


class QuoteRequest(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    form_type = models.CharField(max_length=20)
    page_url = models.CharField(max_length=500, blank=True)
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    state = models.CharField(max_length=60, blank=True)
    details = models.JSONField(default=dict, blank=True)
    message = models.TextField(blank=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.name} ({self.form_type}, {self.created:%Y-%m-%d})"

    def get_admin_url(self):
        return reverse("admin:site_core_quoterequest_change", args=[self.pk])
