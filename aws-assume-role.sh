aws-reset ()
{

	unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY \
		  AWS_SECURITY_TOKEN AWS_SESSION_TOKEN \
		  AWS_ROLE_NAME AWS_ROLE_EXPIRATION
	source "/etc/profile.d/aws-env.sh"
}

assume-role ()
{
	aws-reset
	AWS_ROLE_TMPFILE="$HOME/.aws-role-tmp"
	TOKEN_BIN=$(which get-role-token)

	echo -n "Role name: "
	read ROLE
	echo -n "MFA Token: "
	read TOKEN

	echo -n "Acquiring Token..."
	$TOKEN_BIN $ROLE $TOKEN > $AWS_ROLE_TMPFILE
	if [ $? -eq 0 ] && [ -s $AWS_ROLE_TMPFILE ]; then
		source $AWS_ROLE_TMPFILE
		echo " Installed!"
	else
		echo " Failed"
	fi
}
