document.addEventListener('DOMContentLoaded', () => {
    // Single search elements
    const form = document.getElementById('search-form');
    const input = document.getElementById('address-input');
    const searchBtn = document.getElementById('search-btn');
    const errorMessage = document.getElementById('error-message');
    const loading = document.getElementById('loading');
    const resultCard = document.getElementById('result-card');

    const resAddress = document.getElementById('res-address');
    const resLndcgr = document.getElementById('res-lndcgr');
    const resAreaM2 = document.getElementById('res-area-m2');
    const resAreaPyeong = document.getElementById('res-area-pyeong');
    const resPnu = document.getElementById('res-pnu');
    const resStdrYear = document.getElementById('stdr-year');

    // Batch search elements
    const batchForm = document.getElementById('batch-form');
    const fileInput = document.getElementById('file-input');
    const fileDropArea = document.getElementById('file-drop-area');
    const fileMsg = document.querySelector('.file-msg');
    const batchSubmitBtn = document.getElementById('batch-submit-btn');
    const batchErrorMessage = document.getElementById('batch-error-message');

    // Tab Logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.add('hidden'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.remove('hidden');
            
            // Reset results when switching tabs
            resultCard.classList.add('hidden');
            errorMessage.textContent = '';
            batchErrorMessage.textContent = '';
        });
    });

    // Single Search Logic
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const address = input.value.trim();
        if (!address) return;

        errorMessage.textContent = '';
        resultCard.classList.add('hidden');
        loading.classList.remove('hidden');
        searchBtn.disabled = true;

        try {
            const response = await fetch(`/api/land-area?address=${encodeURIComponent(address)}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '데이터를 불러오는 중 오류가 발생했습니다.');
            }

            resAddress.textContent = data.standard_address;
            resLndcgr.textContent = data.lndcgr;
            resAreaM2.textContent = data.area_m2.toLocaleString();
            resAreaPyeong.textContent = data.area_pyeong.toLocaleString();
            resPnu.textContent = data.pnu;
            resStdrYear.textContent = `기준연도: ${data.stdr_year}년`;

            loading.classList.add('hidden');
            resultCard.classList.remove('hidden');
            
        } catch (error) {
            loading.classList.add('hidden');
            errorMessage.textContent = error.message;
        } finally {
            searchBtn.disabled = false;
        }
    });

    // Batch Upload Logic
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileMsg.textContent = fileInput.files[0].name;
            batchSubmitBtn.disabled = false;
        } else {
            fileMsg.textContent = '엑셀 파일을 드래그하거나 여기를 클릭하세요.';
            batchSubmitBtn.disabled = true;
        }
    });

    fileDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropArea.classList.add('is-active');
    });

    fileDropArea.addEventListener('dragleave', () => {
        fileDropArea.classList.remove('is-active');
    });

    fileDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileDropArea.classList.remove('is-active');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            fileMsg.textContent = fileInput.files[0].name;
            batchSubmitBtn.disabled = false;
        }
    });

    batchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (fileInput.files.length === 0) return;

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        batchErrorMessage.textContent = '';
        loading.classList.remove('hidden');
        batchSubmitBtn.disabled = true;

        try {
            const response = await fetch('/api/batch-process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || '엑셀 처리 중 오류가 발생했습니다.');
            }

            // Handle blob download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            // Get filename from header if possible, else default
            const disposition = response.headers.get('Content-Disposition');
            let filename = 'result.xlsx';
            if (disposition && disposition.indexOf('filename=') !== -1) {
                filename = disposition.split('filename=')[1].replace(/"/g, '');
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (error) {
            batchErrorMessage.textContent = error.message;
        } finally {
            loading.classList.add('hidden');
            batchSubmitBtn.disabled = false;
        }
    });
});
