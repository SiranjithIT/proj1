const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const updateButton = document.getElementById('updateButton');
const deleteButton = document.getElementById('deleteButton');
const updateFormContainer = document.getElementById('updateFormContainer');
const deleteFormContainer = document.getElementById('deleteFormContainer');

fileInput.addEventListener('change', handleFileUpload);
updateButton.addEventListener('click', showUpdateForm);
deleteButton.addEventListener('click', showDeleteForm);

function handleFileUpload(event) {
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload4', {
        method: 'POST',
        body: formData
    })
    .then(() => {
        window.location.href = '/UploadDoc_fin_admin4';
    })
    .catch(error => console.error('Error:', error));
}

function showUpdateForm() {
    deleteFormContainer.innerHTML = "";
    updateFormContainer.innerHTML = `
        <form method="POST" action="/update4">
            <label for="aud">Enter 1 for Auditor 0 for Client:</label>
            <input type="text" id="aud" name="aud" required>
            <label for="aid">Auditor ID:</label>
            <input type="text" id="aid" name="aid" required>
            <label for="uid">User ID:</label>
            <input type="text" id="uid" name="uid" required>
            <button type="submit">Update</button>
        </form>
    `;
}

function showDeleteForm() {
    updateFormContainer.innerHTML = "";
    deleteFormContainer.innerHTML = `
        <form method="POST" action="/delete4">
            <label for="deleteAud">Enter 1 for Auditor 0 for Client:</label>
            <input type="text" id="deleteAud" name="aud" required>
            <label for="deleteId">ID:</label>
            <input type="text" id="deleteId" name="id" required>
            <button type="submit">Delete</button>
        </form>
    `;
}
