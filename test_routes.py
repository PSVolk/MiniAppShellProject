def test_protected_routes(client, auth_client):
    """Тест защищенных маршрутов"""
    # Проверяем, что защищенные маршруты требуют аутентификации
    routes = ['/logout']

    for route in routes:
        # Проверяем без аутентификации
        response = client.get(route, follow_redirects=True)
        assert response.status_code == 200
        assert 'Авторизация' in response.data.decode('utf-8')

        # Проверяем с аутентификацией
        response = auth_client.get(route, follow_redirects=True)
        assert response.status_code == 200