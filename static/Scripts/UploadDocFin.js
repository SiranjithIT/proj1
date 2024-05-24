document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const userId = '{{ user_id }}'; 
    
    fileInput.addEventListener('change', handleFileUpload);

    function handleFileUpload(event) {
        const file = event.target.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', userId); 

        fetch('/upload3', {
            method: 'POST',
            body: formData
        })
        .then(() => {
            window.location.href = '/UploadDoc3';
        })
        .catch(error => console.error('Error:', error));
    }
});
