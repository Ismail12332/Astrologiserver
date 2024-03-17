function showRegistForm() {
        var modal = document.getElementById('RegistForm');
        modal.style.display = 'block';
    }

    function closeRegistForm() {
        var modal = document.getElementById('RegistForm');
        modal.style.display = 'none';
    }

    // Close the modal if the user clicks outside of it
    window.onclick = function(event) {
        var modal = document.getElementById('RegistForm');
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    }


function makeActive(button) {
    // Убираем класс 'active' у всех кнопок
    var buttons = document.querySelectorAll('.knopki button');
    buttons.forEach(function(btn) {
        btn.classList.remove('active');
    });

        // Добавляем класс 'active' только к нажатой кнопке
        button.classList.add('active');
    }