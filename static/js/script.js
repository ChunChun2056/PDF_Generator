document.addEventListener("DOMContentLoaded", () => {
    // Get DOM elements with null checking
    const getElement = (id) => {
      const element = document.getElementById(id);
      if (!element) {
        console.warn(`Element with id '${id}' not found`);
      }
      return element;
    };
  
    // Existing elements
    const logoInput = document.getElementById("logoForm");
    const nameInput = getElement("nameInput");
    const quoteInput = getElement("quoteInput");
    const photoInput = getElement("photoInput");
    const generatePdfBtn = getElement("generatePdfBtn");
    const csvInput = getElement("csvInput");
    const photosZipInput = getElement("photosZipInput");
    const generateBulkPdfsBtn = getElement("generateBulkPdfsBtn");
    const status = getElement("status");
    const popup = getElement("popup");
    const cancelBtn = getElement("cancelBtn");
    const nameColorInput = getElement("nameColorInput");
    const quoteColorInput = getElement("quoteColorInput");
    const bulkNameColorInput = getElement("bulkNameColorInput");
    const bulkQuoteColorInput = getElement("bulkQuoteColorInput");
  
    // Cropping elements
    const cropModal = getElement("cropModal");
    const imageToCrop = getElement("imageToCrop");
    const cropAndSaveButton = getElement("cropAndSaveButton");
    const cancelButton = getElement("cancelButton");
    let cropper;
    let croppedImageData = null;
  
    const tabs = document.querySelectorAll(".tab");
    const tabContents = document.querySelectorAll(".tab-content");
  
    let cancelRequested = false;
    let pdfGenerationStatus = null;
    let checkStatusInterval;
  
    function debugLog(message) {
      console.log(`[Debug] ${message}`);
    }
  
    function showPopup() {
      if (popup) {
        popup.style.display = "flex";
      }
    }
  
    function hidePopup() {
      if (popup) {
        popup.style.display = "none";
      }
    }
  
    function updateStatus(message) {
      if (status) {
        status.textContent = message;
      }
      debugLog(message);
    }
  
    // Tab switching
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        tabContents.forEach((c) => c.classList.remove("active"));
        tab.classList.add("active");
        const targetElement = document.getElementById(tab.dataset.target);
        if (targetElement) {
          targetElement.classList.add("active");
        }
      });
    });
  
    // Function to handle single PDF generation
    function handlePdfGeneration(formData, endpoint, filename) {
      debugLog("Starting individual PDF generation");
      fetch(endpoint, {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((data) => {
              throw new Error(data.error || "Network response was not ok");
            });
          }
          return response.blob();
        })
        .then((blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.style.display = "none";
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          updateStatus("PDF generated successfully!");
        })
        .catch((error) => {
          console.error("Error:", error);
          updateStatus(`Error: ${error.message}`);
        });
    }
  
    // Handle Crop and Save
    cropAndSaveButton.addEventListener("click", () => {
      // Get the cropped canvas
      const croppedCanvas = cropper.getCroppedCanvas();
  
      // Convert to Blob and store the data
      croppedCanvas.toBlob((blob) => {
          croppedImageData = blob;
      });
  
      // Close the modal and reset
      cropModal.style.display = "none";
      cropper.destroy();
    });
  
    // Close Modal (Cancel)
    cancelButton.addEventListener("click", () => {
      cropModal.style.display = "none";
      if (cropper) {
        cropper.destroy();
      }
      photoInput.value = ""; // Clear the file input
    });
  
    // Individual PDF generation
    if (generatePdfBtn) {
      generatePdfBtn.addEventListener("click", () => {
        debugLog("Individual PDF generation button clicked");
  
        // Validate required elements
        if (!logoInput || !nameInput) {
          updateStatus("Error: Required form elements not found");
          return;
        }
  
        const logoFile = logoInput.querySelector('input[type="file"]').files[0];
        if (!logoFile) {
          updateStatus("Please select a logo file.");
          return;
        }
  
        if (!nameInput.value.trim()) {
          updateStatus("Please enter a name.");
          return;
        }
  
        const formData = new FormData();
        formData.append("logo", logoFile);
        formData.append("name", nameInput.value);
        formData.append("quote", quoteInput ? quoteInput.value : "");
  
        // Add the cropped image data if available
        if (croppedImageData) {
          formData.append("photo", croppedImageData, "cropped.jpg");
        }
  
        if (nameColorInput) {
          formData.append("nameColor", nameColorInput.value);
        }
  
        if (quoteColorInput) {
          formData.append("quoteColor", quoteColorInput.value);
        }
  
        updateStatus("Generating PDF...");
        handlePdfGeneration(
          formData,
          "/generate_pdf",
          `${nameInput.value.replace(/ /g, "_")}.pdf`
        );
      });
    }
  
    // Handle Photo Upload
    photoInput.addEventListener("change", (event) => {
      const file = event.target.files[0];
      const reader = new FileReader();
  
      reader.onload = (e) => {
        imageToCrop.src = e.target.result;
        cropModal.style.display = "block";
  
    // Initialize Cropper.js
    if (cropper) {
        cropper.destroy();
      }
      cropper = new Cropper(imageToCrop, {
        aspectRatio: 1.75, // Set the fixed aspect ratio (7cm / 4cm)
        autoCropArea: 1,
        dragMode: "none",
        cropBoxResizable: false,
        viewMode: 1,
      });
    };
  
      if (file) {
        reader.readAsDataURL(file);
      }
    });
  
    function checkStatus() {
      fetch("/check_bulk_pdfs_status")
        .then((response) => response.json())
        .then((data) => {
          debugLog(`Status check response: ${JSON.stringify(data)}`);
          switch (data.status) {
            case "completed":
              clearInterval(checkStatusInterval);
              hidePopup();
              updateStatus("PDFs generated successfully!");
              window.location.href = "/download_zip";
              break;
            case "error":
              clearInterval(checkStatusInterval);
              hidePopup();
              updateStatus(
                `Error generating PDFs (Exit code: ${data.exitcode})`
              );
              break;
            case "cancelled":
              clearInterval(checkStatusInterval);
              hidePopup();
              updateStatus("PDF generation was cancelled.");
              break;
            case "not_started":
              clearInterval(checkStatusInterval);
              hidePopup();
              updateStatus("PDF generation has not started.");
              break;
          }
        })
        .catch((error) => {
          console.error("Error checking status:", error);
          clearInterval(checkStatusInterval);
          hidePopup();
          updateStatus("Error checking generation status.");
        });
    }
  
    // Bulk PDF generation
    if (generateBulkPdfsBtn) {
      generateBulkPdfsBtn.addEventListener("click", function (e) {
        debugLog("Bulk PDF generation button clicked");
        e.preventDefault();
  
        // Validate required elements
        if (!logoInput || !csvInput || !photosZipInput) {
          updateStatus("Error: Required form elements not found");
          return;
        }
  
        // Get file inputs
        const logoFile = logoInput.querySelector('input[type="file"]').files[0];
        const csvFile = csvInput.files[0];
        const zipFile = photosZipInput.files[0];
  
        // Validate files
        if (!logoFile) {
          updateStatus("Please select a logo file.");
          return;
        }
        if (!csvFile) {
          updateStatus("Please select a CSV file.");
          return;
        }
        if (!zipFile) {
          updateStatus("Please select a ZIP file containing photos.");
          return;
        }
  
        debugLog("All files validated, preparing FormData");
        const formData = new FormData();
        formData.append("logo", logoFile);
        formData.append("csv", csvFile);
        formData.append("photosZip", zipFile);
  
        if (bulkNameColorInput) {
          formData.append("nameColor", bulkNameColorInput.value);
        }
        if (bulkQuoteColorInput) {
          formData.append("quoteColor", bulkQuoteColorInput.value);
        }
  
        cancelRequested = false;
        pdfGenerationStatus = "running";
        showPopup();
        updateStatus("Generating PDFs...");
        debugLog("Starting bulk PDF generation request");
  
        fetch("/generate_bulk_pdfs", {
          method: "POST",
          body: formData,
        })
          .then((response) => {
            debugLog(`Server response received: ${response.status}`);
            if (!response.ok) {
              return response.json().then((data) => {
                throw new Error(data.error || "Network response was not ok");
              });
            }
            return response.json();
          })
          .then((data) => {
            debugLog(`Generation started: ${JSON.stringify(data)}`);
            checkStatusInterval = setInterval(checkStatus, 1000);
          })
          .catch((error) => {
            console.error("Error:", error);
            updateStatus(`Error: ${error.message}`);
            pdfGenerationStatus = "error";
            hidePopup();
          });
      });
    }
  
    // Cancel button handler
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        debugLog("Cancel button clicked");
        cancelRequested = true;
        clearInterval(checkStatusInterval);
        fetch("/cancel", { method: "POST" })
          .then((response) => response.json())
          .then((data) => {
            updateStatus(data.message || "PDF generation cancelled.");
            pdfGenerationStatus = "cancelled";
            hidePopup();
          })
          .catch((error) => {
            console.error("Error:", error);
            updateStatus("Error cancelling process.");
            pdfGenerationStatus = "error";
          });
      });
    }
  
    // File input change listeners for debugging
    if (photosZipInput) {
      photosZipInput.addEventListener("change", function (e) {
        debugLog(
          "ZIP file selected: " +
            (e.target.files[0] ? e.target.files[0].name : "No file")
        );
      });
    }
  
    if (csvInput) {
      csvInput.addEventListener("change", function (e) {
        debugLog(
          "CSV file selected: " +
            (e.target.files[0] ? e.target.files[0].name : "No file")
        );
      });
    }
  });