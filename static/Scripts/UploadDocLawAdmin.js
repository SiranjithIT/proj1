const fileInput2 = document.getElementById('fileInput2');
const fileList2 = document.getElementById('fileList2');
const updateButton2 = document.getElementById('updateButton2');
const deleteButton2 = document.getElementById('deleteButton2');
const updateFormContainer2 = document.getElementById('updateFormContainer2');
const deleteFormContainer2 = document.getElementById('deleteFormContainer2');

fileInput2.addEventListener('change', handleFileUpload2);
updateButton2.addEventListener('click', showUpdateForm2);
deleteButton2.addEventListener('click', showDeleteForm2);

function handleFileUpload2(event) {
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload2', {
        method: 'POST',
        body: formData
    })
    .then(() => {
        window.location.href = '/UploadDoc_law_admin2';
    })
    .catch(error => console.error('Error:', error));
}

function showUpdateForm2() {
    deleteFormContainer2.innerHTML = "";
    updateFormContainer2.innerHTML = `
        <form method="POST" action="/update2">
            <label for="aud">Enter 1 for lawyer and 0 for user:</label>
            <input type="text" id="aud" name="aud" required>
            <label for="lid">Lawyer ID:</label>
            <input type="text" id="lid" name="lid" required>
            <label for="uid">User ID:</label>
            <input type="text" id="uid" name="uid" required>
            <button type="submit">Update</button>
        </form>
    `;
}

function showDeleteForm2() {
    updateFormContainer2.innerHTML = "";
    deleteFormContainer2.innerHTML = `
        <form method="POST" action="/delete2">
            <label for="deleteAud2">Enter 1 for lawyer 0 for Client:</label>
            <input type="text" id="deleteAud2" name="aud" required>
            <label for="deleteId2">ID:</label>
            <input type="text" id="deleteId2" name="id" required>
            <button type="submit">Delete</button>
        </form>
    `;
}
