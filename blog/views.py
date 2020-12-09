from django.views import generic
from .models import Post


class PostList(generic.ListView):
    queryset = Post.objects.filter(published=True).order_by('-datetime')


class PostDetail(generic.DetailView):
    model = Post
