const fileInput = document.getElementById('fileInput');
const lawyerId = '{{ lawyer_id }}';

function handleFileUpload() {
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('lawyer_id', lawyerId);

    fetch('/upload1', {
        method: 'POST',
        body: formData
    })
    .then(() => {
        window.location.href = '/upload_doc_lawyer1';
    })
    .catch(error => console.error('Error:', error));
}

document.getElementById('fetchForm').addEventListener('submit', function(event) {
    event.preventDefault();
    fetchFiles();
});

function fetchFiles() {
    const clientId = document.getElementById('client_id').value;
    
    fetch('/fetch_files1', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: 'client_id=' + encodeURIComponent(clientId)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch files');
        }
        return response.text();
    })
    .then(data => {
        const files = data.split(';');
        const fileList1 = document.getElementById('fileList1');
        fileList1.innerHTML = '';
        files.forEach(file => {
            const fileInfo = file.split(',');
            if (fileInfo.length === 2) {
                const li = document.createElement('li');
                li.innerHTML = `<b><i>File Name:</i></b> ${fileInfo[1]}, <a href="/retrieve6/${fileInfo[0]}?filename=${fileInfo[1]}" download="${fileInfo[1]}">Download</a>`;
                fileList1.appendChild(li);
            }
        });
    })
    .catch(error => console.error('Error fetching files:', error));
}
