const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const audId = '{{ aud_id }}'; 

fileInput.addEventListener('change', handleFileUpload);

function handleFileUpload(event) {
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('aud_id', audId); 

    fetch('/upload5', {
        method: 'POST',
        body: formData
    })
    .then(() => {
        window.location.href = '/UploadDoc_auditor5';  
    })
    .catch(error => console.error('Error:', error));
}

document.getElementById('fetchForm').addEventListener('submit', function(event) {
    event.preventDefault(); 
    fetchFiles();
});

function fetchFiles() {
    const clientId = document.getElementById('client_id').value;
    
    fetch('/fetch_files5', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: 'client_id=' + encodeURIComponent(clientId)
    })
    .then(response => {
        if (response.status === 401) {
            throw new Error('Unauthorized access');
        }
        return response.text();
    })
    .then(data => {
        const files = data.split(';');
        const fileList1 = document.getElementById('fileList1');
        fileList1.innerHTML = '';
        files.forEach(file => {
            const fileInfo = file.split(',');
            const li = document.createElement('li');
            li.innerHTML = `<b><i>File Name:</i></b> ${fileInfo[1]}, <a href="/retrieve6/${fileInfo[0]}?filename=${fileInfo[1]}" download="${fileInfo[1]}">Download</a>`;
            fileList1.appendChild(li);
        });
    })
    .catch(error => console.error('Error fetching files:', error));
}
