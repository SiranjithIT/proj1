document.addEventListener('DOMContentLoaded', function() {
  const fileInput = document.getElementById('fileInput');
  const userId = '{{ user_id }}';

  fileInput.addEventListener('change', handleFileUpload9);

  function handleFileUpload9(event) {
      const file = event.target.files[0];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);

      fetch('/upload9', {
          method: 'POST',
          body: formData
      })
      .then(() => {
          window.location.href = '/upload_doc9';
      })
      .catch(error => console.error('Error:', error));
  }
});
