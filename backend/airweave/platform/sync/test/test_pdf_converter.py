"""Test PDF converter with intermediate output visualization.

Run with: pytest airweave/platform/sync/test/test_pdf_converter.py -s -v
"""

import os

import pytest


def print_separator(title: str):
    """Print a nice separator."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


@pytest.mark.asyncio
async def test_pdf_converter_batch_with_intermediate_outputs():
    """Test PDF converter with batch of large files showing all intermediate steps."""
    from airweave.platform.text_converters.pdf_converter import PdfConverter

    print_separator("PDF CONVERTER - BATCH OF LARGE FILES")

    from airweave.platform.sync.test.entities.gdrive import pdf_file

    pdf_path = pdf_file.local_path

    if not os.path.exists(pdf_path):
        print(f"⚠️  Test file not found: {pdf_path}")
        print("Please ensure the test file exists at the expected location")
        return

    # Create converter and reduce max size to 20MB for testing
    converter = PdfConverter()
    converter.max_file_size = 20_000_000  # 20MB for testing

    # Print initial info
    file_size = os.path.getsize(pdf_path)
    max_size_mb = converter.max_file_size / 1_000_000
    print(f"📄 Test File: {os.path.basename(pdf_path)}")
    print(f"   Size: {file_size / 1_000_000:.2f}MB")
    print(f"   Max size setting: {max_size_mb:.0f}MB (reduced for testing)")
    print(f"   Will be split: {'YES ✂️' if file_size > converter.max_file_size else 'NO'}")

    # Create batch with 3 copies of the same large file
    test_files = [pdf_path] * 3
    print(f"\n🔄 Testing batch of {len(test_files)} large files...")
    print(f"   (Processing same file {len(test_files)} times to demonstrate batch OCR)\n")

    # Manually call intermediate methods to show outputs

    # Step 1: Prepare and split
    print_separator("STEP 1: Prepare and Split Files")

    try:
        file_chunks_map = await converter._prepare_and_split_files(test_files)

        total_chunks = 0
        for original_path, chunk_paths in file_chunks_map.items():
            print(f"\nOriginal: {os.path.basename(original_path)}")
            print(f"Chunks: {len(chunk_paths)}")
            total_chunks += len(chunk_paths)

            for i, chunk_path in enumerate(chunk_paths, 1):
                chunk_size = os.path.getsize(chunk_path)
                print(f"  [{i}] {os.path.basename(chunk_path)}: {chunk_size / 1_000_000:.2f}MB")

                if chunk_path != original_path:
                    print("       → Temporary chunk file created")

        print(f"\nTotal files in batch: {len(test_files)}")
        print(f"Total chunks to process: {total_chunks}")

        # If using Mistral
        if converter.mistral_client:
            # Step 2: Upload chunks
            print_separator("STEP 2: Upload Chunks to Mistral")

            upload_map = await converter._upload_chunks_to_mistral(file_chunks_map)

            for chunk_path, upload_info in upload_map.items():
                print(f"Chunk: {os.path.basename(chunk_path)}")
                print(f"  File ID: {upload_info['file_id']}")
                print(f"  Signed URL: {upload_info['signed_url'][:80]}...")

            # Step 3: Create JSONL
            print_separator("STEP 3: Create Batch JSONL")

            jsonl_path, custom_id_to_upload_key = await converter._create_batch_jsonl(upload_map)

            print(f"JSONL path: {jsonl_path}")
            print(f"Entries: {len(custom_id_to_upload_key)}")

            # Show JSONL content
            with open(jsonl_path, "r") as f:
                content = f.read()
                print(f"JSONL content ({len(content)} bytes):")
                print(content[:500])
                if len(content) > 500:
                    print("...")

            # Step 4: Submit job
            print_separator("STEP 4: Submit Batch Job")

            job_id, batch_file_id = await converter._submit_batch_job(jsonl_path)

            print(f"Job ID: {job_id}")
            print(f"Batch file ID: {batch_file_id}")

            # Step 5: Poll
            print_separator("STEP 5: Poll for Completion")

            print("Polling batch job (this may take a while)...")
            print("Progress updates will appear every 10 seconds")

            await converter._poll_batch_job(job_id, timeout=600)

            # Step 6: Download results
            print_separator("STEP 6: Download and Parse Results")

            upload_key_results = await converter._download_batch_results(
                job_id, custom_id_to_upload_key
            )

            for upload_key, markdown in upload_key_results.items():
                print(f"\nUpload Key: {upload_key}")
                if markdown:
                    print(f"  ✅ OCR succeeded ({len(markdown):,} characters)")
                    print(f"  Preview:\n{markdown[:300]}")
                    if len(markdown) > 300:
                        print("  ...")
                else:
                    print("  ❌ OCR failed")

            # Step 7: Combine
            print_separator("STEP 7: Combine Chunk Results")

            final_results = await converter._combine_chunk_results(
                upload_key_results, file_chunks_map
            )

            for i, (original_path, combined_md) in enumerate(final_results.items(), 1):
                print(f"\n[{i}] File: {os.path.basename(original_path)}")
                if combined_md:
                    print(f"  ✅ Final result ({len(combined_md):,} characters)")
                    print(f"  Preview:\n{combined_md[:300]}")
                    if len(combined_md) > 300:
                        print("  ...")
                else:
                    print("  ❌ Conversion failed")

            successful = sum(1 for r in final_results.values() if r)
            total = len(final_results)
            print(f"\n📊 Batch Results: {successful}/{total} files successfully converted")

            # Step 8: Cleanup
            print_separator("STEP 8: Cleanup")

            print("Cleaning up Mistral files...")
            await converter._cleanup_mistral_files(upload_map, batch_file_id)

            print("Cleaning up temp chunks...")
            await converter._cleanup_temp_chunks(file_chunks_map)

            # Delete JSONL
            try:
                os.unlink(jsonl_path)
                print(f"Deleted JSONL: {jsonl_path}")
            except Exception:
                pass

        else:
            print("\n⚠️  No Mistral client available, using PyPDF2 fallback")
            print_separator("PyPDF2 Fallback Processing")

            results = await converter._convert_with_pypdf_batch(test_files)

            for i, (file_path, text) in enumerate(results.items(), 1):
                print(f"\n[{i}] File: {os.path.basename(file_path)}")
                if text:
                    print(f"  ✅ Extraction succeeded ({len(text):,} characters)")
                    print(f"  Preview:\n{text[:300]}")
                    if len(text) > 300:
                        print("  ...")
                else:
                    print("  ❌ Extraction failed")

            successful = sum(1 for r in results.values() if r)
            print(f"\n📊 PyPDF2 Results: {successful}/{len(results)} files successfully converted")

        print("\n" + "=" * 80)
        print("✅ All intermediate steps completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error during intermediate steps: {e}")
        import traceback

        traceback.print_exc()
