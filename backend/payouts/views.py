from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .exceptions import (
    BankAccountNotFound,
    IdempotencyConflict,
    IdempotencyInFlight,
)
from .models import BankAccount, LedgerEntry, Merchant, Payout
from .serializers import (
    BankAccountSerializer,
    LedgerEntrySerializer,
    MerchantSerializer,
    PayoutRequestSerializer,
    PayoutSerializer,
)
from .services import create_payout, get_balance_breakdown


@api_view(['GET'])
def list_merchants(request):
    qs = Merchant.objects.all().order_by('name')
    return Response(MerchantSerializer(qs, many=True).data)


@api_view(['GET'])
def merchant_balance(request, merchant_id):
    if not Merchant.objects.filter(id=merchant_id).exists():
        return Response({'error': 'merchant not found'}, status=404)
    return Response(get_balance_breakdown(merchant_id))


@api_view(['GET'])
def merchant_ledger(request, merchant_id):
    qs = (
        LedgerEntry.objects
        .filter(merchant_id=merchant_id)
        .order_by('-created_at')[:50]
    )
    return Response(LedgerEntrySerializer(qs, many=True).data)


@api_view(['GET'])
def list_bank_accounts(request, merchant_id):
    qs = BankAccount.objects.filter(merchant_id=merchant_id)
    return Response(BankAccountSerializer(qs, many=True).data)


@api_view(['GET'])
def list_payouts(request, merchant_id):
    qs = (
        Payout.objects
        .filter(merchant_id=merchant_id)
        .order_by('-created_at')[:50]
    )
    return Response(PayoutSerializer(qs, many=True).data)


@api_view(['POST'])
def request_payout(request, merchant_id):
    idempotency_key = request.headers.get('Idempotency-Key')
    if not idempotency_key:
        return Response(
            {'error': 'missing Idempotency-Key header'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PayoutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not Merchant.objects.filter(id=merchant_id).exists():
        return Response({'error': 'merchant not found'}, status=404)

    try:
        result = create_payout(
            merchant_id=merchant_id,
            amount_paise=serializer.validated_data['amount_paise'],
            bank_account_id=str(serializer.validated_data['bank_account_id']),
            idempotency_key=idempotency_key,
            request_body=request.data,
        )
    except IdempotencyConflict as e:
        return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
    except IdempotencyInFlight as e:
        # 409 with a Retry-After hint is the convention here
        resp = Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        resp['Retry-After'] = '1'
        return resp
    except BankAccountNotFound as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    return Response(result['body'], status=result['status_code'])
