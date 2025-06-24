document.addEventListener('DOMContentLoaded', function() {

    // Lógica para o filtro de projetos
    const filterButtons = document.querySelectorAll('.filter-btn');
    const projectCards = document.querySelectorAll('.project-card');

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove a classe 'active' de todos os botões
            filterButtons.forEach(btn => btn.classList.remove('active'));
            // Adiciona a classe 'active' ao botão clicado
            button.classList.add('active');

            const filter = button.getAttribute('data-filter');

            projectCards.forEach(card => {
                const category = card.getAttribute('data-category');

                if (filter === 'todos' || filter === category) {
                    card.style.display = 'flex'; // Usar flex para manter o layout interno
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

});