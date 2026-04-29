from django.contrib import admin
from django.urls import path
from biblioteca_app import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # AUTENTICAÇÃO E DASHBOARD
    path('login/', views.login_view, name='login_view'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login_view'), name='logout'),
    path('', views.home, name='home'),

    # ACERVO
    path('acervo/buscar/', views.estoque, name='estoque'),
    path('acervo/cadastrar/', views.cadastro_livros, name='cadastro_livros'),
    path('acervo/editar/<int:livro_id>/', views.editar_livro, name='editar_livro'),
    path('acervo/excluir/<int:livro_id>/', views.excluir_livro, name='excluir_livro'),
    path('acervo/detalhes/<int:livro_id>/', views.livro_detalhes, name='livro_detalhes'),

    # CIRCULAÇÃO
    path('circulacao/emprestimo/', views.emprestimo, name='emprestimo'),
    path('circulacao/emprestimo/<int:livro_id>/', views.emprestimo_com_livro, name='emprestimo_com_livro'),
    path('circulacao/devolucoes/', views.reservas, name='reservas'),
    path('circulacao/devolver/<int:emprestimo_id>/', views.devolver_livro, name='devolver_livro'),
    path('circulacao/renovacao/', views.renovacao, name='renovacao'),
    path('circulacao/reservas/', views.fila_reservas, name='fila_reservas'),

    # LEITORES
    path('leitores/buscar/', views.usuarios, name='leitores'),
    path('leitores/cadastrar/', views.cadastro_leitor, name='cadastro_leitor'),
    path('leitores/editar/<int:leitor_id>/', views.editar_leitor, name='editar_leitor'),
    path('leitores/excluir/<int:leitor_id>/', views.excluir_leitor, name='excluir_leitor'),
    path('leitores/historico/<int:leitor_id>/', views.historico_leitor, name='historico_leitor'),

    # FINANCEIRO
    path('financeiro/multas/', views.multa, name='multa'),
    path('financeiro/historico/', views.historico_financeiro, name='historico_financeiro'),

    # ADMINISTRAÇÃO
    path('admin-sys/funcionarios/', views.configuracao_contas, name='configuracao_contas'),
    path('admin-sys/funcionarios/cadastrar/', views.configuracao_cadastro, name='configuracao_cadastro'),
    path('admin-sys/funcionarios/excluir/<int:user_id>/', views.excluir_usuario, name='excluir_usuario'),
    path('admin-sys/relatorios/', views.relatorio, name='relatorio'),
    path('admin-sys/configuracoes/', views.configuracao_multa, name='configuracao_multa'),

    # APIs (JSON endpoints)
    path('api/leitor/buscar/', views.buscar_leitor, name='buscar_leitor'),
    path('api/leitor/buscar_por_id/', views.buscar_leitor_por_id, name='buscar_leitor_por_id'),
    path('api/livro/buscar/', views.buscar_livro, name='buscar_livro'),
    path('api/livro/buscar_por_id/', views.buscar_livro_por_id, name='buscar_livro_por_id'),
    path('api/livro/completo/', views.buscar_livro_completo, name='buscar_livro_completo'),
    path('api/exemplar/buscar/', views.buscar_exemplar, name='buscar_exemplar'),
    path('api/calcular_multa/', views.calcular_multa, name='calcular_multa'),

    # RECUPERAÇÃO DE SENHA
    path('reset-password/', auth_views.PasswordResetView.as_view(template_name="reset_password.html"), name="password_reset"),
    path('reset-password-sent/', auth_views.PasswordResetDoneView.as_view(template_name="reset_password_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="reset_password_confirm.html"), name="password_reset_confirm"),
    path('reset-password-complete/', auth_views.PasswordResetCompleteView.as_view(template_name="reset_password_complete.html"), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)