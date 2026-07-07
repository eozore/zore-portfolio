# -*- coding: utf-8 -*-
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools import db

def check_session(session_id):
    if db is None:
        print("❌ Firestore not initialized.")
        return
        
    try:
        doc_ref = db.collection('csm_sessions').document(session_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            print(f"✅ SESSION FOUND: {session_id}")
            print(f"   Created At: {data.get('createdAt')}")
            print(f"   Category: {data.get('category')}")
            messages = data.get('messages', [])
            print(f"   Total Messages: {len(messages)}")
            print("\n=== Transcript ===")
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown').upper()
                text = msg.get('text', '')
                print(f"[{i+1}] {role}: {text[:150]}...")
        else:
            print(f"❌ Session {session_id} not found in Firestore.")
    except Exception as e:
        print(f"❌ Error checking session: {e}")

if __name__ == "__main__":
    session_id = "4d0e220c-7fb5-4c6a-9a6d-730e756c82ac"
    check_session(session_id)
