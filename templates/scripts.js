document.addEventListener('DOMContentLoaded', function() {
    const analysisButtons = document.querySelectorAll('.list-group-item-action');

    analysisButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const analysisType = event.target.getAttribute('data-type');
            fetch(`/analisis/${analysisType}`, {
                method: 'GET',
            })
            .then(response => response.json())
            .then(data => {
                displayResults(data);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    });

    function displayResults(data) {
        const resultadosDiv = document.getElementById('resultadosSection');
        resultadosDiv.innerHTML = '';
        
        if (data.error) {
            resultadosDiv.innerHTML = `<p>${data.error}</p>`;
            return;
        }
        
        const resultTable = document.createElement('table');
        resultTable.classList.add('table', 'table-striped');
        const headers = Object.keys(data.resultados[0]);
        
        const headerRow = document.createElement('tr');
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        resultTable.appendChild(headerRow);
        
        data.resultados.forEach(row => {
            const tr = document.createElement('tr');
            headers.forEach(header => {
                const td = document.createElement('td');
                td.textContent = row[header];
                tr.appendChild(td);
            });
            resultTable.appendChild(tr);
        });
        
        resultadosDiv.appendChild(resultTable);
    }
});
