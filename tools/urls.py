from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('pdf/', views.pdf_tools, name='pdf'),
    path('images/', views.image_tools, name='images'),
    
    # PDF operations
    path('api/pdf/merge/', views.merge_pdf, name='merge_pdf'),
    path('api/pdf/delete-page/', views.delete_page, name='delete_page'),
    path('api/pdf/to-images/', views.pdf_to_images, name='pdf_to_images'),
    path('api/images/to-pdf/', views.images_to_pdf, name='images_to_pdf'),
    path('api/pdf/watermark/', views.watermark_pdf, name='watermark_pdf'),
    path('api/pdf/encrypt/', views.encrypt_pdf, name='encrypt_pdf'),
    path('api/pdf/compress/', views.compress_pdf, name='compress_pdf'),
    
    # Image operations
    path('api/image/resize-pixels/', views.resize_pixels, name='resize_pixels'),
    path('api/image/resize-filesize/', views.resize_filesize, name='resize_filesize'),
    path('api/image/crop/', views.crop_image, name='crop_image'),
    path('api/image/compress/', views.compress_image, name='compress_image'),
    path('api/image/collage/', views.create_collage, name='create_collage'),
]
