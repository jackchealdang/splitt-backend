from logging import raiseExceptions
import os
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

load_dotenv()
app = FastAPI()

endpoint = os.getenv("AZURE_ENDPOINT", "")
key = os.getenv("AZURE_KEY", "")

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=endpoint, credential=AzureKeyCredential(key)
)


origins = ["http://localhost", "https://localhost", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process-receipt/")
async def process_receipt(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-receipt", AnalyzeDocumentRequest(bytes_source=file_content)
        )
        receipts = poller.result()
        if receipts is None or receipts.documents is None:
            raise ValueError("No documents found.")

        for idx, receipt in enumerate(receipts.documents):
            if receipt.fields is None:
                continue

            print("--------Recognizing receipt #{}--------".format(idx + 1))
            receipt_type = receipt.doc_type
            if receipt_type:
                print("Receipt Type: {}".format(receipt_type))
            merchant_name = receipt.fields.get("MerchantName")
            if merchant_name:
                print(
                    "Merchant Name: {} has confidence: {}".format(
                        merchant_name.value_string, merchant_name.confidence
                    )
                )
            transaction_date = receipt.fields.get("TransactionDate")
            if transaction_date:
                print(
                    "Transaction Date: {} has confidence: {}".format(
                        transaction_date.value_date, transaction_date.confidence
                    )
                )
            if receipt.fields.get("Items"):
                print("Receipt items:")
                items = receipt.fields.get("Items")
                if items is None or items.value_array is None:
                    continue

                itemsArray = items
                for idx, item in enumerate(items.value_array):
                    print("...Item #{}".format(idx + 1))

                    if item.value_object is None:
                        continue
                    item_description = item.value_object.get("Description")
                    if item_description:
                        print(
                            "......Item Description: {} has confidence: {}".format(
                                item_description.value_string,
                                item_description.confidence,
                            )
                        )
                    item_quantity = item.value_object.get("Quantity")
                    if item_quantity:
                        print(
                            "......Item Quantity: {} has confidence: {}".format(
                                item_quantity.value_number, item_quantity.confidence
                            )
                        )
                    item_price = item.value_object.get("Price")
                    if item_price and item_price.value_currency:
                        print(
                            "......Individual Item Price: {} has confidence: {}".format(
                                item_price.value_currency.amount, item_price.confidence
                            )
                        )
                    item_total_price = item.value_object.get("TotalPrice")
                    if item_total_price and item_total_price.value_currency:
                        print(
                            "......Total Item Price: {} has confidence: {}".format(
                                item_total_price.value_currency.amount,
                                item_total_price.confidence,
                            )
                        )
            subtotal = receipt.fields.get("Subtotal")
            if subtotal and subtotal.value_currency:
                print(
                    "Subtotal: {} has confidence: {}".format(
                        subtotal.value_currency.amount, subtotal.confidence
                    )
                )
            tax = receipt.fields.get("TotalTax")
            if tax and tax.value_currency:
                print(
                    "Tax: {} has confidence: {}".format(
                        tax.value_currency.amount, tax.confidence
                    )
                )
            tip = receipt.fields.get("Tip")
            print(receipt.fields)
            if tip and tip.value_currency:
                print(
                    "Tip: {} has confidence: {}".format(
                        tip.value_currency.amount, tip.confidence
                    )
                )
            total = receipt.fields.get("Total")
            if total and total.value_currency:
                print(
                    "Total: {} has confidence: {}".format(
                        total.value_currency.amount, total.confidence
                    )
                )
            print("--------------------------------------")

        itemsArray = []

        if receipts and receipts.documents:
            receipt = receipts.documents[0]
            if receipt.fields:
                items = receipt.fields.get("Items")
                if items and items.value_array:
                    for item in items.value_array:
                        if item.value_object:
                            descriptionField = item.value_object.get("Description")
                            quantityField = item.value_object.get("Quantity")
                            priceField = item.value_object.get("TotalPrice")
                            currItem = {
                                "name": getattr(descriptionField, "value_string", None)
                                if descriptionField
                                else None,
                                "qty": getattr(quantityField, "value_number", None)
                                if quantityField
                                else None,
                                "price": getattr(
                                    getattr(priceField, "value_currency", None),
                                    "amount",
                                    0,
                                ),
                            }
                            itemsArray.append(currItem)
                taxField = receipt.fields.get("TotalTax")
                tax = getattr(getattr(taxField, "value_currency", None), "amount", 0)
                tipField = receipt.fields.get("Tip")
                tip = getattr(getattr(tipField, "value_currency", None), "amount", 0)

                data = {
                    "items": itemsArray,
                    "tax": tax,
                    "tip": tip,
                }

                return {"success": True, "data": data}
        else:
            raise ValueError("No documents found.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
